# -*- coding: utf-8 -*-
"""End-to-end example playbook check.

``docs/examples/`` and ``playbooks/`` are the copy-paste entry point to this
collection: a new user's first real run is one of these files, usually with
their own account's ids pasted into the ``vars`` block. They are also the
one part of the repository that CI structurally cannot verify -- running
them means creating billable Tencent Cloud resources, so no workflow does
it. Nothing else looked at them either, which made them the only artefacts
in the tree that could rot silently: rename a module option, drop a role
variable, or delete a role and every test stays green while the golden path
in the README becomes a wall of "Unsupported parameters" and "undefined
variable" errors.

This check closes that gap statically. For every playbook it asserts that

* the file is valid YAML and a list of plays (``yaml``),
* every ``susunola.tencentcloud.<module>`` action resolves to a module that
  ships in ``plugins/modules/`` (``modules``),
* every option passed to such a module is declared by the module's
  ``DOCUMENTATION`` or by one of the doc fragments it extends
  (``options``) -- this is the check that catches a renamed option, which
  is otherwise only visible at run time as an API-shaped error,
* every ``role:`` entry resolves to a role in ``roles/`` (``roles``),
* every ``tc_<role>_*`` variable handed to a role is declared in that
  role's ``defaults/main.yml`` (``role-vars``) -- role defaults are the
  role's public interface, so a variable that is not there is either a
  typo or a variable the role no longer honours,
* every variable a play dereferences is reachable: declared in the play's
  ``vars``, registered by a task, set by ``set_fact``, documented as an
  extra var in the file (``-e name=``), guarded by an ``is defined`` test,
  or one of the well-known names in ``ALLOWED_UNDEFINED`` (``vars``).

Nothing here connects to Tencent Cloud, so it runs in CI in under a
second. It cannot prove a playbook *works* -- only that it is not
referencing things that no longer exist. That is exactly the failure mode
a copied example hits first.

Run with ``--check`` (used in CI) to fail on any problem; run without
arguments to print the example inventory (what each playbook uses and how
the chain fits together). ``--json`` emits the same inventory as JSON for
docs tooling.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - CI installs pyyaml before this runs
    yaml = None

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULES_DIR = REPO_ROOT / "plugins" / "modules"
ROLES_DIR = REPO_ROOT / "roles"
DOC_FRAGMENTS_DIR = REPO_ROOT / "plugins" / "doc_fragments"

# Directories holding playbooks a user is meant to copy. Adding a file to
# either directory enrols it in this check automatically.
EXAMPLE_DIRS = ("docs/examples", "playbooks")

#: Integration targets are checked with the same rules; a test can point this
#: at a throwaway tree the way it points MODULES_DIR at one.
TARGETS_DIR = REPO_ROOT / "tests" / "integration" / "targets"

COLLECTION = "susunola.tencentcloud"
COLLECTION_PREFIX = COLLECTION + "."

# Task and play keys that are Ansible syntax rather than module options.
ANSIBLE_KEYWORDS = {
    "action", "any_errors_fatal", "args", "async", "become", "become_method",
    "become_user", "block", "changed_when", "check_mode", "collections",
    "connection", "delay", "delegate_facts", "delegate_to", "diff",
    "environment", "failed_when", "force_handlers", "gather_facts",
    "handlers", "hosts", "ignore_errors", "ignore_unreachable", "listen",
    "local_action", "loop", "loop_control", "max_fail_percentage", "module_defaults",
    "name", "no_log", "notify", "order", "poll", "port", "post_tasks",
    "pre_tasks", "register", "remote_user", "rescue", "retries", "roles",
    "run_once", "serial", "strategy", "tags", "tasks", "throttle", "timeout",
    "until", "vars", "vars_files", "vars_prompt", "when", "with_items",
    "with_dict", "with_list", "with_fileglob", "with_first_found",
    "with_inventory_hostnames", "with_lines", "with_nested", "with_sequence",
    "with_subelements", "with_together",
}

# Task keys whose value is a Jinja expression rather than a template string.
CONDITION_KEYS = ("when", "until", "failed_when", "changed_when")

# Names a playbook may reference without declaring them: Ansible's own
# magic variables, the loop variable, and the credential/region environment
# convention every module in this collection falls back to (the module
# resolves those, not the playbook, which is why they never appear in vars).
ALLOWED_UNDEFINED = {
    "item", "ansible_facts", "ansible_failed_task", "ansible_failed_result",
    "ansible_play_hosts", "ansible_play_batch", "ansible_version",
    "groups", "group_names", "inventory_hostname", "inventory_hostname_short",
    "omit", "play_hosts", "playbook_dir", "inventory_dir", "role_name",
    "tencentcloud_region", "tencentcloud_secret_id", "tencentcloud_secret_key",
    "tencentcloud_token", "tencentcloud_profile",
    # Ansible's own settings, readable from any play or task.
    "ansible_playbook_python", "ansible_python_interpreter", "ansible_connection",
    "ansible_user", "ansible_host", "ansible_port", "ansible_check_mode",
}

# Jinja/Python literals that look like names inside an expression.
JINJA_KEYWORDS = {
    "and", "else", "false", "for", "if", "in", "is", "none", "not", "or",
    "true", "undefined", "False", "None", "True",
}

JINJA_REF_RE = re.compile(r"{{\s*(.*?)\s*}}", re.S)
CONDITION_RE = re.compile(r"(?:\bwhen\b|\buntil\b|\bfailed_when\b|\bchanged_when\b)\s*:\s*(.+?)\s*$", re.M)
GUARDED_RE = re.compile(r"([A-Za-z_]\w*)\s+is\s+(?:defined|undefined)")
#: ``x is <test>`` -- the right-hand side is a Jinja test, never a variable.
JINJA_TEST_RE = re.compile(r"\bis\s+(?:not\s+)?[A-Za-z_]\w*")
EXTRA_VAR_RE = re.compile(r"-e\s+([A-Za-z_]\w*)\s*=")
IDENT_RE = re.compile(r"(?<![.\w'\"])([A-Za-z_]\w*)")


# --------------------------------------------------------------------------
# module and role metadata
# --------------------------------------------------------------------------

def _load_documentation(path):
    """Return the parsed DOCUMENTATION mapping from a plugin or fragment file."""
    try:
        source = path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "DOCUMENTATION":
                try:
                    value = ast.literal_eval(node.value)
                except ValueError:
                    return None
                if not isinstance(value, str):
                    return None
                try:
                    parsed = yaml.safe_load(value)
                except Exception:
                    return None
                return parsed if isinstance(parsed, dict) else None
    return None


def module_options(name, cache=None):
    """Return the option names a module accepts, doc fragments included.

    ``region`` and the other shared options are not in the module's own
    ``DOCUMENTATION``: they come from the fragments listed under
    ``extends_documentation_fragment``. Without those, every example that
    passes ``region`` would look like it used an undeclared option.
    """
    cache = {} if cache is None else cache
    if name in cache:
        return cache[name]
    options = set()
    doc = _load_documentation(MODULES_DIR / (name + ".py"))
    if doc is not None:
        options.update((doc.get("options") or {}).keys())
        fragments = doc.get("extends_documentation_fragment") or []
        if isinstance(fragments, str):
            fragments = [fragments]
        for fragment in fragments:
            short = fragment.rsplit(".", 1)[-1]
            frag_doc = _load_documentation(DOC_FRAGMENTS_DIR / (short + ".py"))
            if frag_doc is not None:
                options.update((frag_doc.get("options") or {}).keys())
    cache[name] = options
    return options


def role_default_vars(role, cache=None):
    """Return the variable names a role declares in defaults/main.yml."""
    cache = {} if cache is None else cache
    if role in cache:
        return cache[role]
    names = set()
    defaults = ROLES_DIR / role / "defaults" / "main.yml"
    if defaults.is_file():
        try:
            parsed = yaml.safe_load(defaults.read_text(encoding="utf-8"))
        except Exception:
            parsed = None
        if isinstance(parsed, dict):
            names.update(str(key) for key in parsed)
    cache[role] = names
    return names


# --------------------------------------------------------------------------
# playbook walking
# --------------------------------------------------------------------------

def discover(roots=None):
    """Return every example playbook path, sorted."""
    roots = EXAMPLE_DIRS if roots is None else roots
    found = []
    for root in roots:
        base = REPO_ROOT / root
        if not base.is_dir():
            continue
        found.extend(sorted(base.glob("*.yml")))
    return sorted(found)


def iter_task_blocks(tasks):
    """Yield every task mapping, descending into block/rescue/always.

    The `vars:` of a wrapping task is copied onto each of the tasks inside it,
    so a block that declares its variables applies them here too.
    """
    for task in tasks or []:
        if not isinstance(task, dict):
            continue
        yield task
        inherited = task.get("vars") if isinstance(task.get("vars"), dict) else {}
        for key in ("block", "rescue", "always"):
            nested = task.get(key)
            if isinstance(nested, list):
                for inner in iter_task_blocks(nested):
                    if inherited and isinstance(inner.get("vars"), dict):
                        merged = dict(inherited)
                        merged.update(inner["vars"])
                        inner = dict(inner, vars=merged)
                    elif inherited:
                        inner = dict(inner, vars=dict(inherited))
                    yield inner


def task_action(task):
    """Return (fqcn, params) for a task's module call, or (None, None).

    Handles the plain ``module: params`` form and the ``action:`` /
    ``local_action:`` long form. Ansible keywords are filtered out of the
    params, so what is left is what the module will actually receive.
    """
    candidates = []
    for key, value in task.items():
        if key in ANSIBLE_KEYWORDS:
            continue
        if isinstance(value, dict):
            candidates.append((key, value))
        elif isinstance(value, str) and value.strip():
            candidates.append((key, {}))
    if not candidates:
        for key in ("action", "local_action"):
            value = task.get(key)
            if isinstance(value, dict):
                module = value.get("module")
                if isinstance(module, str):
                    params = dict(value)
                    params.pop("module", None)
                    return module.strip(), params
            elif isinstance(value, str) and value.strip():
                return value.strip().split()[0], {}
        return None, None
    # Prefer the collection's own modules: a task almost never names two.
    for name, params in candidates:
        if name.startswith(COLLECTION_PREFIX):
            return name, params
    return candidates[0]


#: A Jinja function call (``lookup(...)``) and a keyword argument
#: (``resource_type='vpc'``) both look like names to a tokeniser. Neither is a
#: variable read, and both appear in the roles' lookups.
JINJA_CALL_RE = re.compile(r"\b([A-Za-z_]\w*)\s*\(")
JINJA_KWARG_RE = re.compile(r"[(,]\s*[A-Za-z_]\w*\s*=")


def expression_names(expression):
    """Return the bare variable names a Jinja expression reads.

    Filters are dropped (everything after the first ``|``): the variable
    itself is on the left, and the filter names are not variables. An
    ``X is defined`` test is removed too -- ``defined`` is not a variable,
    and the name it guards is allowed to be absent by definition. Function
    calls and keyword arguments are removed as well: ``lookup(...)`` and
    ``resource_type='vpc'`` are not reads of ``lookup`` or ``resource_type``.
    """
    names = set()
    expression = GUARDED_RE.sub("", str(expression))
    expression = JINJA_TEST_RE.sub("", expression)
    for chunk in expression.split("|")[:1]:
        # Calls first: masking a keyword argument inserts a "(", and a call
        # removal running afterwards would then eat the argument in front of
        # it (``tc_demo_name, resource_type=`` became ``tc_demo_name(``).
        chunk = JINJA_CALL_RE.sub("", chunk)
        chunk = JINJA_KWARG_RE.sub("(", chunk)
        for match in IDENT_RE.finditer(chunk):
            name = match.group(1)
            if name not in JINJA_KEYWORDS:
                names.add(name)
    return names


def play_variable_names(play):
    """Return every variable name a play dereferences anywhere."""
    names = set()
    for task in iter_task_blocks(play.get("tasks") or []):
        for key, value in task.items():
            if key in CONDITION_KEYS:
                names.update(expression_names(value))
                continue
            if isinstance(value, dict):
                names.update(_walk_templates(value))
            elif isinstance(value, (list, tuple)):
                names.update(_walk_templates(list(value)))
            elif isinstance(value, str):
                names.update(_walk_templates(value))
    for role in play.get("roles") or []:
        names.update(_walk_templates(role))
    return names


def _walk_templates(value):
    """Return the variable names referenced inside an arbitrary structure."""
    names = set()
    if isinstance(value, str):
        for match in JINJA_REF_RE.finditer(value):
            names.update(expression_names(match.group(1)))
    elif isinstance(value, dict):
        for item in value.values():
            names.update(_walk_templates(item))
    elif isinstance(value, (list, tuple)):
        for item in value:
            names.update(_walk_templates(item))
    return names


def play_defined_names(play):
    """Return the variable names a play makes available."""
    defined = set()
    play_vars = play.get("vars")
    if isinstance(play_vars, dict):
        defined.update(str(key) for key in play_vars)
    for task in iter_task_blocks(play.get("tasks") or []):
        register = task.get("register")
        if isinstance(register, str) and register:
            defined.add(register)
        defined.update(_set_fact_keys(task))
        # A task may declare its own vars, and the integration targets do it
        # constantly: the payload a later task compares against is built in a
        # `vars:` block on the task that creates it. Counting them is what
        # makes this checker usable on a task list as well as on a playbook.
        declared = task.get("vars")
        if isinstance(declared, dict):
            defined.update(str(key) for key in declared)
        for key in ("loop_control",):
            control = task.get(key)
            if isinstance(control, dict) and isinstance(control.get("loop_var"), str):
                defined.add(control["loop_var"])
    return defined


def role_published_names(role, cache=None):
    """Return the variable names a role publishes to later tasks and plays.

    That is everything the role assigns with ``set_fact`` plus everything it
    ``register``s: both are host-level and outlive the role, which is how a
    chained playbook hands stage one's ids to stage two. They are
    deliberately absent from ``defaults/main.yml``, which holds the role's
    *inputs*. Without this, a play that consumes a role's result would look
    like it read an undefined variable.
    """
    cache = {} if cache is None else cache
    if role in cache:
        return cache[role]
    published = set()
    tasks_dir = ROLES_DIR / role / "tasks"
    for task_file in sorted(tasks_dir.rglob("*.yml")) if tasks_dir.is_dir() else []:
        try:
            parsed = yaml.safe_load(task_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(parsed, dict):
            parsed = parsed.get("tasks") or []
        for task in iter_task_blocks(parsed):
            published.update(_set_fact_keys(task))
            register = task.get("register")
            if isinstance(register, str) and register:
                published.add(register)
    cache[role] = published
    return published


def _set_fact_keys(task):
    """Return the keys a task assigns through set_fact."""
    for key in ("ansible.builtin.set_fact", "set_fact"):
        value = task.get(key)
        if isinstance(value, dict):
            return {str(name) for name in value}
    return set()


def role_entries(play):
    """Yield (role_name, vars_mapping) for every role the play applies."""
    for entry in play.get("roles") or []:
        if isinstance(entry, str):
            yield entry, {}
        elif isinstance(entry, dict):
            name = entry.get("role") or entry.get("name")
            if isinstance(name, str):
                role_vars = entry.get("vars")
                yield name, role_vars if isinstance(role_vars, dict) else {}


# --------------------------------------------------------------------------
# checks
# --------------------------------------------------------------------------

def display_path(path):
    """Return the repo-relative path when there is one, the path otherwise."""
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def check_tasks(tasks, path, label, cache, inventory, published, extra_vars, guarded, problems):
    """Check one list of tasks: module names resolve, options are declared, and
    every variable read is defined somewhere.

    Shared by the example playbooks and the integration targets. A target is a
    list of tasks rather than a play, and the same rules apply to it -- with
    more at stake, because a target only runs in the credentialed weekly job
    (and eight of them never run at all), so an option name that no longer
    exists costs a real run against a real account to discover.
    """
    for task in iter_task_blocks(tasks):
        fqcn, params = task_action(task)
        if fqcn is None or not fqcn.startswith(COLLECTION_PREFIX):
            continue
        short = fqcn[len(COLLECTION_PREFIX):]
        inventory["modules"].add(short)
        if not (MODULES_DIR / (short + ".py")).is_file():
            problems.append(("modules", "%s: %s calls %s, which is not in plugins/modules/"
                             % (path.name, label, fqcn)))
            continue
        declared = module_options(short, cache["modules"])
        if not declared:
            # The DOCUMENTATION block could not be parsed; saying
            # "every option is undeclared" would be worse than silence.
            continue
        for key in sorted(params):
            if key in ANSIBLE_KEYWORDS:
                continue
            if key not in declared:
                problems.append(("options", "%s: %s passes %s to %s, which does not declare that option"
                                 % (path.name, label, key, short)))

    play = {"tasks": list(tasks)}
    referenced = play_variable_names(play)
    defined = play_defined_names(play)
    for name in sorted(referenced):
        if name in ALLOWED_UNDEFINED or name in JINJA_KEYWORDS:
            continue
        if name in defined or name in published or name in extra_vars or name in guarded:
            continue
        problems.append(("vars", "%s: %s reads %s, which is not declared in vars, registered, "
                         "documented as an extra var or guarded with 'is defined'"
                         % (path.name, label, name)))


def discover_targets():
    """Return every integration target task file, sorted."""
    return sorted(TARGETS_DIR.glob("*/tasks/*.yml")) if TARGETS_DIR.is_dir() else []


def discover_role_tasks():
    """Return every role task file, sorted."""
    if not ROLES_DIR.is_dir():
        return []
    return sorted(ROLES_DIR.glob("*/tasks/**/*.yml"))


def role_vars_vars(role, cache):
    """Return the names ``roles/<role>/vars/main.yml`` declares."""
    cache = {} if cache is None else cache
    if role in cache:
        return cache[role]
    names = set()
    path = ROLES_DIR / role / "vars" / "main.yml"
    if path.is_file():
        try:
            parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception:
            parsed = None
        if isinstance(parsed, dict):
            names.update(str(key) for key in parsed)
    cache[role] = names
    return names


def role_defined_names(role, cache):
    """Return every name the role defines in any of its task files.

    A role's task files are included from each other, so a ``set_fact``,
    ``register``, task ``vars`` or custom ``loop_var`` in one file is in scope
    in the file it includes. Reading them per file instead reported every such
    handoff -- ``_tc_rabbitmq_vhost`` is a ``loop_var`` in ``main.yml`` used by
    ``virtual_host.yml`` -- as an undefined variable.
    """
    cache = {} if cache is None else cache
    if role in cache:
        return cache[role]
    names = set()
    tasks_dir = ROLES_DIR / role / "tasks"
    files = sorted(tasks_dir.rglob("*.yml")) if tasks_dir.is_dir() else []
    for task_file in files:
        try:
            parsed = yaml.safe_load(task_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(parsed, dict):
            parsed = parsed.get("tasks") or []
        if isinstance(parsed, list):
            names |= play_defined_names({"tasks": parsed})
    cache[role] = names
    return names


def check_role_tasks(path, cache=None):
    """Return (problems, inventory) for one role task file.

    A role's own tasks were the one place a module call went unchecked: the
    example playbooks and the integration targets are validated, but the 68
    roles only ever ran in a real account, so a renamed option or a module
    that no longer exists would surface as a user's failed playbook. The
    scope is the role's: its ``defaults/main.yml`` inputs, its
    ``vars/main.yml``, and everything it ``set_fact``s or ``register``s
    anywhere in the role.
    """
    cache = {"modules": {}, "roles": {}, "facts": {}, "role_vars": {},
             "role_defined": {}} if cache is None else cache
    cache.setdefault("role_vars", {})
    cache.setdefault("role_defined", {})
    problems = []
    relative = path.relative_to(ROLES_DIR)
    role = relative.parts[0]
    label = "role %s (%s)" % (role, relative.parts[-1])
    inventory = {"path": display_path(path), "plays": 1, "modules": set(),
                 "roles": {role}}
    text = path.read_text(encoding="utf-8")
    try:
        parsed = yaml.safe_load(text)
    except Exception as exc:
        problems.append(("yaml", "%s is not valid YAML: %s" % (relative, exc)))
        return problems, inventory
    if parsed is None:
        return problems, inventory
    if isinstance(parsed, dict):
        parsed = parsed.get("tasks") or []
    if not isinstance(parsed, list):
        problems.append(("yaml", "%s is not a list of tasks" % relative))
        return problems, inventory

    published = set(role_default_vars(role, cache["roles"]))
    published |= role_vars_vars(role, cache["role_vars"])
    published |= role_published_names(role, cache["facts"])
    published |= role_defined_names(role, cache["role_defined"])
    check_tasks(parsed, path, label, cache, inventory, published,
                set(EXTRA_VAR_RE.findall(text)), set(GUARDED_RE.findall(text)),
                problems)
    return problems, inventory


def check_target(path, cache=None):
    """Return (problems, inventory) for one integration target task file."""
    cache = {"modules": {}, "roles": {}, "facts": {}} if cache is None else cache
    problems = []
    inventory = {"path": display_path(path), "plays": 1, "modules": set(), "roles": set()}
    text = path.read_text(encoding="utf-8")
    target = path.parent.parent.name
    label = "target %s" % target
    try:
        tasks = yaml.safe_load(text)
    except Exception as exc:
        problems.append(("yaml", "%s is not valid YAML: %s" % (path.name, exc)))
        return problems, inventory
    if tasks is None:
        return problems, inventory
    if not isinstance(tasks, list):
        problems.append(("yaml", "%s is not a list of tasks" % path.name))
        return problems, inventory

    # A target's variables live in its own vars/main.yml as well as in the
    # task list, and its inputs are materialised there by
    # scripts/integration_inputs.py.
    published = set()
    vars_file = path.parent.parent / "vars" / "main.yml"
    if vars_file.is_file():
        try:
            declared = yaml.safe_load(vars_file.read_text(encoding="utf-8"))
        except Exception:
            declared = None
        if isinstance(declared, dict):
            published.update(str(key) for key in declared)
    for task in iter_task_blocks(tasks):
        published.update(_set_fact_keys(task))

    check_tasks(tasks, path, label, cache, inventory,
                published, set(EXTRA_VAR_RE.findall(text)), set(GUARDED_RE.findall(text)), problems)
    return problems, inventory


def check_playbook(path, cache=None):
    """Return (problems, inventory) for one playbook file."""
    cache = {"modules": {}, "roles": {}, "facts": {}} if cache is None else cache
    problems = []
    inventory = {
        "path": display_path(path),
        "plays": 0,
        "modules": set(),
        "roles": set(),
    }

    text = path.read_text(encoding="utf-8")
    extra_vars = set(EXTRA_VAR_RE.findall(text))
    guarded = set(GUARDED_RE.findall(text))

    try:
        plays = yaml.safe_load(text)
    except Exception as exc:
        problems.append(("yaml", "%s is not valid YAML: %s" % (path.name, exc)))
        return problems, inventory
    if not isinstance(plays, list) or not plays:
        problems.append(("yaml", "%s is not a list of plays" % path.name))
        return problems, inventory

    # What a role publishes reaches any play in the file, not only the play
    # that applied the role: that handoff is what makes a chained playbook
    # work.
    published = set()
    for play in plays:
        if not isinstance(play, dict):
            continue
        for name, _role_vars in role_entries(play):
            if name.startswith(COLLECTION_PREFIX):
                published.update(role_published_names(name[len(COLLECTION_PREFIX):], cache["facts"]))
        play_vars = play.get("vars")
        if isinstance(play_vars, dict):
            # The play's own vars are as much in scope as a registered result;
            # check_tasks only sees the task list, so they are handed over here.
            published.update(str(key) for key in play_vars)
        for task in iter_task_blocks(play.get("tasks") or []):
            published.update(_set_fact_keys(task))

    for play in plays:
        if not isinstance(play, dict):
            problems.append(("yaml", "%s contains a play that is not a mapping" % path.name))
            continue
        inventory["plays"] += 1
        label = play.get("name") or "(unnamed play)"

        for name, role_vars in role_entries(play):
            if not name.startswith(COLLECTION_PREFIX):
                continue
            short = name[len(COLLECTION_PREFIX):]
            inventory["roles"].add(short)
            if not (ROLES_DIR / short).is_dir():
                problems.append(("roles", "%s: play %r uses role %s, which is not in roles/"
                                 % (path.name, label, short)))
                continue
            declared = role_default_vars(short, cache["roles"])
            for key in sorted(role_vars):
                if declared and str(key) not in declared:
                    problems.append(("role-vars", "%s: play %r passes %s, which role %s does not declare in defaults/main.yml"
                                     % (path.name, label, key, short)))
                elif not declared:
                    problems.append(("roles", "%s: role %s has no readable defaults/main.yml, so its variables cannot be checked"
                                     % (path.name, short)))

        check_tasks(play.get("tasks") or [], path, label, cache, inventory,
                    published, extra_vars, guarded, problems)

    return problems, inventory


def check(roots=None, targets=True, roles=True):
    """Return (problems, inventories) for every discovered playbook, target and
    role task file.

    The integration targets are checked with the same rules as the example
    playbooks: a target is a list of tasks rather than a play, and it needs the
    same guarantees -- that the modules it names exist, that the options it
    passes exist, and that the variables it reads are defined somewhere. A
    target gets less feedback than a playbook does: it runs only in the
    credentialed weekly job, and eight of them are gated and never dispatched,
    so a renamed option would be found by a real run against a real account.
    """
    cache = {"modules": {}, "roles": {}, "facts": {}}
    problems = []
    inventories = []
    paths = discover(roots)
    if not paths:
        problems.append(("discovery", "no example playbooks found under %s" % ", ".join(EXAMPLE_DIRS)))
    for path in paths:
        found, inventory = check_playbook(path, cache)
        problems.extend(found)
        inventories.append(inventory)
    if targets:
        target_paths = discover_targets()
        if not target_paths:
            problems.append(("discovery", "no integration targets found under tests/integration/targets"))
        for path in target_paths:
            found, inventory = check_target(path, cache)
            problems.extend(found)
            inventories.append(inventory)
    if roles:
        role_paths = discover_role_tasks()
        if not role_paths:
            problems.append(("discovery", "no role task files found under roles/"))
        for path in role_paths:
            found, inventory = check_role_tasks(path, cache)
            problems.extend(found)
            inventories.append(inventory)
    return problems, inventories


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def print_inventory(inventories):
    """Print what each example playbook uses."""
    for inventory in inventories:
        modules = ", ".join(sorted(inventory["modules"])) or "-"
        roles = ", ".join(sorted(inventory["roles"])) or "-"
        print("%s" % inventory["path"])
        print("  plays:   %d" % inventory["plays"])
        print("  roles:   %s" % roles)
        print("  modules: %s" % modules)
    print("%d example playbook(s)" % len(inventories))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true",
                        help="fail on any problem instead of printing the inventory")
    parser.add_argument("--json", action="store_true",
                        help="print the inventory as JSON")
    parser.add_argument("--path", action="append", default=None,
                        help="directory to scan (repeatable); defaults to %s"
                             % ", ".join(EXAMPLE_DIRS))
    parser.add_argument("--no-targets", dest="targets", action="store_false",
                        help="skip the integration targets, which are checked too")
    parser.add_argument("--no-roles", dest="roles", action="store_false",
                        help="skip the role task files, which are checked too")
    args = parser.parse_args(argv)

    if yaml is None:
        print("PyYAML is required (pip install pyyaml)", file=sys.stderr)
        return 2

    problems, inventories = check(args.path, targets=args.targets,
                                  roles=args.roles)

    if args.json:
        print(json.dumps(
            [dict(item, modules=sorted(item["modules"]), roles=sorted(item["roles"]))
             for item in inventories],
            indent=2, sort_keys=True))
        return 1 if problems else 0

    if args.check:
        if problems:
            print("example playbook problems:", file=sys.stderr)
            for kind, detail in problems:
                print("  - [%s] %s" % (kind, detail), file=sys.stderr)
            return 1
        print("examples: %d playbook/target/role file(s) checked" % len(inventories))
        return 0

    print_inventory(inventories)
    if problems:
        print("problems:", file=sys.stderr)
        for kind, detail in problems:
            print("  - [%s] %s" % (kind, detail), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
