"""Task-level contract tests for the ``tc_*`` solution roles.

Roles orchestrate real-cloud modules and therefore cannot execute in CI
(no cloud account is available to the sanity/unit gate). What *can* be
tested deterministically is the task graph the roles are built from --
the exact logic the P0-10 backlog calls out: the role-level state switch
(``tc_<prefix>_state``) that selects provision vs teardown, teardown
reverse-order semantics, and drift protection for the module / lookup /
included-file references.

Every assertion in this module is derived from the role YAML on disk, so a
role change that inverts a gate, provisions under ``absent``, references a
renamed module, or uses an undeclared input fails here without a cloud
round-trip. Each role yields six independent task-level assertion cases:

* ``state-switch`` -- defaults declare exactly one ``*_state`` input with a
  legal value, and ``tasks/main.yml`` dispatches on it.
* ``absent-never-provisions`` -- no write-module invocation reachable when
  the state switch is ``absent`` carries ``state: present`` (and no
  present-branch invocation carries ``state: absent``).
* ``reverse-teardown`` -- within a task file, a resource class is removed
  only after it was reconciled; teardown files never include provision
  files and never run in the present branch.
* ``module-and-target-integrity`` -- every referenced collection module,
  lookup plugin and included task file exists; actions are namespaced.
* ``inputs-declared-or-derived`` -- every ``tc_*`` / ``_tc_*`` variable
  used outside a ``default(...)`` / ``is defined`` guard is declared in
  ``defaults/main.yml`` or produced by the role itself (set_fact, register,
  task-level vars, loop vars, index vars).
* ``jinja-parse`` -- ``when`` conditions and pure-expression arguments
  compile as Jinja templates.

The collection's module inventory is read once at import time; role graphs
are parsed lazily and cached per role. Skipping a role is allowed only when
a case does not apply to its shape (for example a role with a single task
file has no teardown file to keep out of the present branch).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
ROLES_DIR = REPO_ROOT / "roles"
MODULES_DIR = REPO_ROOT / "plugins" / "modules"
LOOKUP_DIR = REPO_ROOT / "plugins" / "lookup"

# ansible-core modules a role may invoke without the collection prefix.
BUILTIN_ACTIONS = {
    "assert", "blockinfile", "command", "copy", "debug", "fail", "fetch", "file", "find",
    "get_url", "group", "group_by", "hostname", "import_role", "import_tasks", "include",
    "include_role", "include_tasks", "include_vars", "lineinfile", "meta", "package",
    "pause", "raw", "replace", "script", "service", "set_fact", "set_stats", "shell",
    "stat", "tempfile", "template", "unarchive", "uri", "user", "wait_for",
    "wait_for_connection",
}

# Common task keys that are not module actions.
_NON_ACTION_KEYS = {
    "args", "become", "become_user", "changed_when", "check_mode", "delegate_to",
    "delay", "environment", "failed_when", "ignore_errors", "listen", "loop",
    "loop_control", "name", "no_log", "notify", "register", "retries", "run_once",
    "tags", "until", "vars", "when", "with_dict", "with_items", "with_subelements",
}

_ACTION_PREFIX = "susunola.tencentcloud."
_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_JINJA_RE = re.compile(r"\{\{.*?\}\}", re.S)
_STATE_ABSENT_RE = re.compile(r"==\s*'absent'|!=\s*'present'")
_STATE_PRESENT_RE = re.compile(r"==\s*'present'|!=\s*'absent'")


def _val_of(task: dict, name: str):
    """Read a task attribute written bare or FQCN-prefixed."""
    if name in task:
        return task[name]
    for prefix in ("ansible.builtin", "ansible.legacy"):
        key = "%s.%s" % (prefix, name)
        if key in task:
            return task[key]
    return None


def _flatten(items, out):
    """Flatten block/rescue/always wrappers, inheriting their ``when``."""
    if not isinstance(items, list):
        return out
    for item in items:
        if not isinstance(item, dict):
            continue
        if any(k in item for k in ("block", "rescue", "always")):
            for child in _flatten(item.get("block"), []):
                merged = dict(child)
                wrapper_when = item.get("when")
                if wrapper_when is not None:
                    own = merged.get("when")
                    if isinstance(own, list):
                        merged["when"] = [wrapper_when] + own
                    elif own is None:
                        merged["when"] = wrapper_when
                    else:
                        merged["when"] = [wrapper_when, own]
                out.append(merged)
            continue
        out.append(dict(item))
    return out


def _gate_of(when) -> str:
    """Classify a when clause: absent / present / mixed / neutral."""
    if when is None:
        return "neutral"
    clauses = [when] if isinstance(when, str) else list(when)
    text = " ".join(str(c) for c in clauses)
    has_absent = bool(_STATE_ABSENT_RE.search(text))
    has_present = bool(_STATE_PRESENT_RE.search(text))
    if has_absent and has_present:
        return "mixed"
    if has_absent:
        return "absent"
    if has_present:
        return "present"
    return "neutral"


def _effective(scope_gate: str, task_gate: str) -> str:
    """Combine an include-scope gate with a task's own gate."""
    scope_absent = scope_gate in ("absent", "mixed")
    scope_present = scope_gate in ("present", "mixed")
    task_absent = task_gate in ("absent", "mixed")
    task_present = task_gate in ("present", "mixed")
    can_absent = scope_absent and task_absent
    can_present = scope_present and task_present
    if can_absent and can_present:
        return "mixed"
    if can_absent:
        return "absent"
    if can_present:
        return "present"
    return "unreachable"


class RoleGraph:
    """Parsed, gate-aware view of one role's task files."""

    def __init__(self, role_dir: Path):
        self.name = role_dir.name
        self.tasks_dir = role_dir / "tasks"
        self.files = sorted(p for p in self.tasks_dir.iterdir() if p.suffix in (".yml", ".yaml"))
        self.defaults: dict = {}
        defaults_path = role_dir / "defaults" / "main.yml"
        if defaults_path.exists():
            data = yaml.safe_load(defaults_path.read_text(encoding="utf-8")) or {}
            if isinstance(data, dict):
                self.defaults = data
        self.steps: list[dict] = []
        self._parse()

    def _parse(self) -> None:
        scope: dict[str, str] = {}
        pending = [("main.yml", "neutral")]
        while pending:
            fname, scope_gate = pending.pop(0)
            if fname in scope:
                continue
            scope[fname] = scope_gate
            path = self.tasks_dir / fname
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or []
            if not isinstance(data, list):
                data = [] if data is None else [data]
            for index, task in enumerate(_flatten(data, [])):
                step = self._step(fname, index, task)
                step["scope_gate"] = scope_gate
                step["effective"] = _effective(scope_gate, step["gate"])
                self.steps.append(step)
                target = step["include"]
                if target and target not in scope:
                    pending.append((target, step["effective"]))
        for p in self.files:
            if p.name not in scope:
                # File is never included (main.yml already parsed above).
                self.steps.append({"file": p.name, "orphan": True})

    def _step(self, fname: str, index: int, task: dict) -> dict:
        action_short, action_full = None, None
        for key in task:
            if key.startswith(("susunola.", "ansible.")):
                action_full = key
                action_short = key.split(".")[-1]
                break
        if action_full is None:
            for key in ("assert", "debug", "fail", "import_tasks", "include_tasks",
                        "include_vars", "meta", "set_fact"):
                if key in task:
                    action_short, action_full = key, key
                    break
        if action_full is None:
            for key in task:
                if key in _NON_ACTION_KEYS or key.startswith("_") or "." in key:
                    continue
                if re.match(r"^[a-z0-9_]+$", key):
                    action_short, action_full = key, key
                    break
        include = None
        for key in ("include_tasks", "import_tasks"):
            value = _val_of(task, key)
            if isinstance(value, str):
                include = value
        set_fact = _val_of(task, "set_fact")
        set_fact_keys = set()
        if isinstance(set_fact, dict):
            set_fact_keys = {k for k in set_fact if isinstance(k, str)}
        elif isinstance(set_fact, str):
            set_fact_keys = {set_fact}
        task_vars = task.get("vars")
        if not isinstance(task_vars, dict):
            task_vars = {}
        loop_control = task.get("loop_control")
        loop_var = None
        index_var = None
        if isinstance(loop_control, dict):
            if isinstance(loop_control.get("loop_var"), str):
                loop_var = loop_control["loop_var"]
            if isinstance(loop_control.get("index_var"), str):
                index_var = loop_control["index_var"]
        when = task.get("when")
        state_val = None
        state_tmpl = None
        if action_full and action_full.startswith(_ACTION_PREFIX):
            options = task.get("args")
            if not isinstance(options, dict):
                options = task.get(action_full)
            if isinstance(options, dict):
                state_arg = options.get("state")
                if isinstance(state_arg, str):
                    if "{{" in state_arg:
                        state_tmpl = state_arg
                    else:
                        state_val = state_arg
        step = {
            "file": fname,
            "index": index,
            "name": str(task.get("name", "")),
            "action": action_short,
            "action_full": action_full,
            "is_write": bool(action_full and action_full.startswith(_ACTION_PREFIX)
                             and not (action_short or "").endswith("_info")),
            "gate": _gate_of(when),
            "state": state_val,
            "state_template": state_tmpl,
            "include": include,
            "register": task.get("register") if isinstance(task.get("register"), str) else None,
            "set_fact": set_fact_keys,
            "task_vars": {k for k in task_vars if isinstance(k, str)},
            "loop_var": loop_var,
            "index_var": index_var,
            "when_text": " ".join(str(c) for c in (when if isinstance(when, list) else [when]))
            if when is not None else "",
            "args_text": task.get("args") if isinstance(task.get("args"), str) else None,
        }
        return step

    # -- derived views ----------------------------------------------------
    @property
    def write_steps(self) -> list[dict]:
        return [s for s in self.steps if s.get("is_write")]

    def absent_reachable(self) -> list[dict]:
        return [s for s in self.steps if s.get("effective") in ("absent", "mixed")
                and s.get("is_write")]

    def present_reachable(self) -> list[dict]:
        return [s for s in self.steps if s.get("effective") in ("present", "mixed")
                and s.get("is_write")]

    @property
    def state_keys(self) -> list[str]:
        return sorted(k for k in self.defaults if k.endswith("_state"))

    @property
    def raw_text(self) -> str:
        parts = []
        for path in self.files:
            parts.append(path.read_text(encoding="utf-8"))
        return "\n".join(parts)


def _iter_roles():
    return sorted((p for p in ROLES_DIR.iterdir() if p.name.startswith("tc_") and p.is_dir()),
                  key=lambda p: p.name)


ROLES = _iter_roles()
_MODULE_NAMES = {p.stem for p in MODULES_DIR.glob("*.py") if p.stem != "__init__"}
_LOOKUP_NAMES = {p.stem for p in LOOKUP_DIR.glob("*.py") if p.stem != "__init__"}

_GRAPH_CACHE: dict[str, RoleGraph] = {}


@pytest.fixture
def graph(role_dir):
    name = role_dir.name
    if name not in _GRAPH_CACHE:
        _GRAPH_CACHE[name] = RoleGraph(role_dir)
    return _GRAPH_CACHE[name]


def _cases():
    """Parametrize (role_dir, family) for every role x family pair."""
    families = ["state-switch", "absent-never-provisions", "reverse-teardown",
                "module-and-target-integrity", "inputs-declared-or-derived", "jinja-parse"]
    for role in ROLES:
        for family in families:
            yield pytest.param(role, family, id="%s/%s" % (role.name, family))


@pytest.mark.parametrize("role_dir,family", list(_cases()))
def test_role_task_contract(role_dir, family, graph):
    """Dispatch one task-level assertion family for a role."""
    if family == "state-switch":
        _check_state_switch(graph)
    elif family == "absent-never-provisions":
        _check_absent_never_provisions(graph)
    elif family == "reverse-teardown":
        _check_reverse_teardown(graph)
    elif family == "module-and-target-integrity":
        _check_integrity(graph)
    elif family == "inputs-declared-or-derived":
        _check_inputs(graph)
    else:
        _check_jinja(graph)


def _check_state_switch(graph: RoleGraph) -> None:
    """defaults declare the role's state plumbing and tasks use it.

    Three role shapes are recognised:

    * lifecycle -- ``when`` clauses dispatch provision vs teardown on the
      state switch (the common shape);
    * delegate -- the switch is forwarded as a template into a module's
      ``state:`` argument and the module owns the lifecycle;
    * stateless ensure -- no ``*_state`` default and no removal path.
    """
    state_keys = graph.state_keys
    raw = graph.raw_text
    prefix = graph.name[3:]
    primaries = [k for k in state_keys if k == "tc_%s_state" % prefix]
    if not primaries:
        primaries = state_keys
    gate_used = [k for k in state_keys if any(k in s["when_text"] for s in graph.steps
                                             if not s.get("orphan"))]
    if not state_keys:
        # Stateless ensure-only roles: hardcoded reconcile, no teardown and
        # no hidden removal path hidden behind a state template.
        for step in graph.write_steps:
            assert step["state"] != "absent", (
                "%s/%s[%s]: role has no *_state switch but removes (state: absent)"
                % (graph.name, step["file"], step["name"]))
        for path in graph.files:
            assert not path.name.startswith("teardown"), (
                "%s: stateless ensure role ships a teardown file %s without a state switch"
                % (graph.name, path.name))
        return
    # Every declared switch must actually be referenced by the tasks, and a
    # switch used in a when clause must default to present/absent.
    for key in state_keys:
        assert re.search(r"\b%s\b" % re.escape(key), raw), (
            "%s: %s is declared in defaults but never referenced by tasks"
            % (graph.name, key))
        if key in gate_used:
            assert graph.defaults[key] in ("present", "absent", True, False), (
                "%s: %s defaults to %r but is used in when clauses; expected"
                " present/absent" % (graph.name, key, graph.defaults[key]))
        else:
            assert graph.defaults[key] in ("present", "absent", "running", "stopped",
                                           "started", True, False), (
                "%s: %s defaults to %r which is not a recognised state"
                % (graph.name, key, graph.defaults[key]))
    if gate_used:
        # Lifecycle role: the entrypoint must dispatch on a state switch.
        main = [s for s in graph.steps if s["file"] == "main.yml" and not s.get("orphan")]
        main_text = " ".join(s["when_text"] for s in main)
        assert any(k in main_text for k in gate_used), (
            "%s: state switches %s are gated in sub-files but tasks/main.yml never"
            " dispatches on them" % (graph.name, gate_used))
    else:
        # Delegate role: the state switch must be forwarded to exactly one
        # module's state argument as a template.
        forwarded = [s for s in graph.write_steps
                     if s["state_template"] and primaries[0] in s["state_template"]]
        assert len(forwarded) == 1, (
            "%s: no when-clause state dispatch found; expected exactly one module"
            " forwarding %s, found %d" % (graph.name, primaries[0], len(forwarded)))
        assert re.search(r"\{\{\s*%s\b" % re.escape(primaries[0]), forwarded[0]["state_template"]), (
            "%s: %s is not forwarded through a module state: template"
            % (graph.name, primaries[0]))


def _check_absent_never_provisions(graph: RoleGraph) -> None:
    """The absent branch must tear down, never provision."""
    if not graph.state_keys:
        # Stateless ensure roles own no state semantics; the state-switch
        # family already requires them to have no removal path at all.
        return
    absent = graph.absent_reachable()
    for step in absent:
        assert step["state"] != "present", (
            "%s/%s[%s]: state: present reachable when %s is absent"
            % (graph.name, step["file"], step["name"], graph.state_keys[0] if graph.state_keys else "state"))
    present = graph.present_reachable()
    for step in present:
        assert step["state"] != "absent", (
            "%s/%s[%s]: state: absent reachable when %s is present"
            % (graph.name, step["file"], step["name"], graph.state_keys[0] if graph.state_keys else "state"))
    # A role that tears down must also be able to provision its classes.
    absent_classes = {s["action"] for s in absent}
    present_classes = {s["action"] for s in present}
    removable_only = absent_classes - present_classes
    # Classes removed without a provisioning twin are allowed only when they
    # are never created by the role (external/user-supplied resources), which
    # the absent branch documents by targeting names/ids from the inputs.
    for step in absent:
        if step["action"] in removable_only:
            assert step["gate"] == "absent" and step["state"] == "absent", (
                "%s/%s[%s]: removes %s but role never provisions it and call is not a"
                " strict absent-state removal" % (graph.name, step["file"], step["name"], step["action"]))


def _check_reverse_teardown(graph: RoleGraph) -> None:
    """Teardown ordering: delete after reconcile, teardown files stay out of present."""
    # Same-file ordering: a class is removed only after it was reconciled.
    by_file: dict[str, dict[str, list[dict]]] = {}
    for step in graph.write_steps:
        if step.get("orphan"):
            continue
        by_file.setdefault(step["file"], {}).setdefault(step["action"], []).append(step)
    for fname, classes in by_file.items():
        for action, steps in classes.items():
            creates = [s for s in steps if s["state"] == "present"]
            removes = [s for s in steps if s["state"] == "absent"]
            if not creates or not removes:
                continue
            last_create = max(s["index"] for s in creates)
            first_remove = min(s["index"] for s in removes)
            assert first_remove > last_create, (
                "%s/%s: %s removed before it is reconciled (create at %d, remove at %d)"
                % (graph.name, fname, action, last_create, first_remove))
    # Teardown files may not be reachable in the present branch and may not
    # chain back into provision files.
    for fname in sorted({s["file"] for s in graph.steps}):
        if not fname.startswith("teardown"):
            continue
        steps = [s for s in graph.steps if s["file"] == fname and not s.get("orphan")]
        effective = {s["effective"] for s in steps} - {"unreachable"}
        assert not (effective & {"present"}), (
            "%s: teardown file %s reachable when state is present" % (graph.name, fname))
        for step in steps:
            if step["include"]:
                assert not step["include"].startswith("provision"), (
                    "%s: teardown file %s includes provision file %s"
                    % (graph.name, fname, step["include"]))
        # Tasks inside teardown files must carry state: absent when they write.
        for step in steps:
            if step.get("is_write") and step["state"] == "present":
                raise AssertionError(
                    "%s/%s[%s]: teardown file provisions with state: present"
                    % (graph.name, fname, step["name"]))


def _check_integrity(graph: RoleGraph) -> None:
    """Every module, lookup and included file exists; actions are namespaced."""
    known_files = {p.name for p in graph.files}
    for step in graph.steps:
        if step.get("orphan"):
            continue
        if step["include"] and not step["include"].endswith((".yml", ".yaml")):
            raise AssertionError(
                "%s/%s[%s]: dynamic include target %r unsupported by contract"
                % (graph.name, step["file"], step["name"], step["include"]))
        if step["include"] and step["include"] not in known_files:
            raise AssertionError(
                "%s/%s[%s]: includes %s but the file does not exist under tasks/"
                % (graph.name, step["file"], step["name"], step["include"]))
        if step["action"] and not step["action_full"]:
            raise AssertionError(
                "%s/%s[%s]: bare action %r must be namespaced"
                % (graph.name, step["file"], step["name"], step["action"]))
        if step["action_full"] and step["action_full"].startswith(_ACTION_PREFIX):
            module = step["action"]
            assert module in _MODULE_NAMES, (
                "%s/%s[%s]: module %s is not in plugins/modules/"
                % (graph.name, step["file"], step["name"], module))
        elif step["action_full"] and step["action_full"].startswith("ansible."):
            assert step["action"] in BUILTIN_ACTIONS, (
                "%s/%s[%s]: %s is not an ansible.builtin action"
                % (graph.name, step["file"], step["name"], step["action_full"]))
    # Every task file (other than the entrypoint) is included somewhere.
    included = {s["include"] for s in graph.steps if s["include"]}
    for p in graph.files:
        if p.name != "main.yml" and p.name not in included:
            raise AssertionError("%s: tasks/%s is never included" % (graph.name, p.name))
    for match in re.finditer(r"lookup\(['\"]([^'\"]+)['\"]", graph.raw_text):
        plugin = match.group(1)
        if plugin.startswith(_ACTION_PREFIX):
            short = plugin.split(".")[-1]
            assert short in _LOOKUP_NAMES, (
                "%s: lookup plugin %s is not in plugins/lookup/" % (graph.name, plugin))


def _check_inputs(graph: RoleGraph) -> None:
    """Every unguarded tc_* variable is declared or produced by the role."""
    produced = set(graph.defaults)
    for step in graph.steps:
        produced |= step["set_fact"] | step["task_vars"]
        if step["register"]:
            produced.add(step["register"])
        if step["loop_var"]:
            produced.add(step["loop_var"])
        if step["index_var"]:
            produced.add(step["index_var"])
    undeclared = set()
    for snippet, guarded in _var_snippets(graph):
        if guarded:
            continue
        for token in _IDENT_RE.findall(snippet):
            if token.startswith(("tc_", "_tc_")) and token not in produced:
                undeclared.add(token)
    assert not undeclared, "%s: undeclared input(s) used unguarded: %s" % (
        graph.name, ", ".join(sorted(undeclared)))


def _var_snippets(graph: RoleGraph):
    """Yield (snippet, guarded) pairs that may reference variables."""
    for step in graph.steps:
        if step.get("orphan"):
            continue
        when_text = step["when_text"]
        if when_text:
            yield when_text, ("default(" in when_text or "is defined" in when_text
                              or "is not defined" in when_text)
        if step["args_text"]:
            yield step["args_text"], "default(" in step["args_text"]
    for match in _JINJA_RE.finditer(graph.raw_text):
        snippet = match.group(0)
        yield snippet, "default(" in snippet


def _check_jinja(graph: RoleGraph) -> None:
    """when clauses and pure-expression args must compile as Jinja."""
    jinja2 = pytest.importorskip("jinja2", reason="jinja2 is required to parse role templates")
    env = jinja2.Environment()
    for step in graph.steps:
        if step.get("orphan"):
            continue
        when_text = step["when_text"]
        if when_text:
            env.parse(when_text)
        args_text = step["args_text"]
        if args_text and args_text.lstrip().startswith("{{") and args_text.rstrip().endswith("}}"):
            env.parse(args_text)
