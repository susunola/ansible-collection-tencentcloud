#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Verify that every SDK reference resolves at the *declared* minimum SDK.

Why
---
``requirements.txt`` declares ``tencentcloud-sdk-python`` as a compatibility
range, so the collection promises that the floor of that range works. Nothing
checked that promise. CI installed the range (which floats to the newest
release) and then re-pinned the SDK to ``GENERATED_SDK_VERSION`` before
checking anything, so the release named as the minimum was never the release
under test -- and three ``_info`` modules were generated from products that do
not exist at the declared floor at all (``edgezone``, ``databuddy`` and
``workbuddyenterprise`` only appear in newer SDK releases).

A version range is a claim about the oldest supported release. This guard is
what makes the claim checkable instead of aspirational.

What it checks
--------------
* Every ``from tencentcloud.<product>.<api-version> import ...`` in
  ``plugins/`` resolves: the product package, the ``*_client``/``models``
  submodules, and the ``*Client`` class each module instantiates. A class is
  verified against the client modules reachable from the plugin tree, plus the
  ``<product>.<api-version>`` string tables in ``RESOURCE_SPECS``-style
  constants, so a renamed SDK class is caught here instead of crashing a user
  at runtime.
* Every spec in ``scripts/info_specs_auto.py`` names a service package, client
  module, client class and request class that exist.
* The COS modules' separate ``qcloud_cos`` SDK imports resolve.
* The SDK installed here is *exactly* the release ``requirements.txt``
  declares as its floor, so a green run verifies the floor the collection
  documents rather than a range nobody installed.

Usage
-----
    python scripts/check_sdk_floor.py            # the census
    python scripts/check_sdk_floor.py --check    # exit 1 on any finding
"""

from __future__ import absolute_import, division, print_function

import argparse
import ast
import importlib
import importlib.util
import re
import sys
from importlib.metadata import PackageNotFoundError, version as dist_version
from pathlib import Path

__metaclass__ = type

REPO_ROOT = Path(__file__).resolve().parents[1]
REQUIREMENTS_PATH = REPO_ROOT / "requirements.txt"

PLUGIN_DIRS = ("modules", "module_utils", "plugin_utils", "inventory",
               "lookup", "action", "event_source")

#: ``tencentcloud-sdk-python>=3.1.180,<4.0.0`` -> (">=3.1.180", "<4.0.0")
SDK_REQUIREMENT_RE = re.compile(r"^[ \t]*tencentcloud-sdk-python[ \t]*([^#\n]*)",
                                re.M)

#: A product package, e.g. ``tencentcloud.cvm.v20170312``.
SERVICE_RE = re.compile(r"^tencentcloud\.[a-z0-9_]+\.[a-z0-9_]+$")

#: The ``<product>.<api-version>`` strings used by the hand-written tables.
SERVICE_STRING_RE = re.compile(r"^([a-z0-9_]+)\.(v[0-9]+)$")

CLIENT_SUFFIX = "Client"

#: COS is not API 3.0; its modules use the separate qcloud_cos SDK.
COS_PACKAGE = "qcloud_cos"


def declared_range(path=REQUIREMENTS_PATH):
    """Return ``(floor, cap)`` from the SDK requirement, or ``None`` per part.

    Only the operators this project uses are interpreted (``>=`` and ``<``);
    anything else returns ``None`` so the caller reports it instead of
    guessing at a floor it did not read.
    """
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError:
        return None, None
    match = SDK_REQUIREMENT_RE.search(text)
    if not match:
        return None, None
    floor = cap = None
    for part in match.group(1).split(","):
        part = part.strip()
        if part.startswith(">="):
            floor = part[2:].strip()
        elif part.startswith("<"):
            cap = part.lstrip("<=").strip()
    return floor, cap


def installed_version():
    """Return the tencentcloud-sdk-python version in this environment."""
    try:
        return dist_version("tencentcloud-sdk-python")
    except PackageNotFoundError:
        pass
    try:
        import tencentcloud
        return tencentcloud.__version__
    except ImportError:
        raise RuntimeError(
            "tencentcloud-sdk-python is not installed; install "
            "requirements.txt first (python -m pip install -r requirements.txt)")


def _import(import_path):
    """Import *import_path*; return ``(module, error_message)``."""
    try:
        return importlib.import_module(import_path), None
    except Exception as exc:  # noqa: BLE001 - the exception text is the finding
        return None, "%s: %s" % (type(exc).__name__, exc)


def _plugin_sources(root=REPO_ROOT):
    """Return ``(relative_path, path)`` for every plugin source file."""
    sources = []
    for directory in PLUGIN_DIRS:
        plugin_root = Path(root) / "plugins" / directory
        if not plugin_root.is_dir():
            continue
        for path in sorted(plugin_root.rglob("*.py")):
            sources.append((str(path.relative_to(root)), path))
    return sources


def _sdk_imports(tree):
    """Return ``(service_packages, client_modules)`` imported by *tree*.

    *client_modules* holds ``(local_name, service_package, submodule)`` so an
    aliased client module (``... import alb_client as cm``) resolves to the
    module the class attribute belongs to.
    """
    packages = set()
    clients = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or not node.module:
            continue
        if not SERVICE_RE.match(node.module):
            continue
        packages.add(node.module)
        for alias in node.names:
            if alias.name.endswith("_client"):
                clients.append((alias.asname or alias.name, node.module,
                                alias.name))
    return packages, clients


def _models_locals(tree):
    """Return the local names bound to a ``models`` submodule in *tree*.

    ``models.FileClient`` is a model class that merely ends in ``Client``; it
    is not an SDK client and must not be verified as one.
    """
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module \
                and SERVICE_RE.match(node.module):
            for alias in node.names:
                if alias.name == "models":
                    names.add(alias.asname or alias.name)
    return names


def _service_strings(tree):
    """Return ``(product, api_version)`` pairs named by string literals."""
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            match = SERVICE_STRING_RE.match(node.value)
            if match:
                found.add((match.group(1), match.group(2)))
    return found


def _dynamic_clients(tree):
    """Return client modules named by service strings instead of imports.

    ``plugins/lookup/resource_id.py`` and ``module_utils/inventory.py`` build
    clients with ``importlib`` from tables such as
    ``("vpc.v20170312", "VpcClient", ...)`` or from a literal package path
    (``package = "tencentcloud.sts.v20180813"``), so the SDK package never
    appears in an import statement.
    """
    clients = set()
    packages = {"tencentcloud.%s.%s" % product for product in _service_strings(tree)}
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                and SERVICE_RE.match(node.value):
            packages.add(node.value)
    for package in packages:
        product = package.split(".")[1]
        clients.add((package, product + "_client"))
        clients.add((package, "models"))
    return clients


def _client_class_references(tree):
    """Return the SDK client class names *tree* references.

    Attribute references are always class lookups. A ``*Client`` *string* is
    only treated as a class name in files that carry a
    ``<product>.<api-version>`` table -- elsewhere it is data (an option
    value such as the accepted ``supported_client`` values), not an SDK class.
    """
    models_locals = _models_locals(tree)
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr.endswith(CLIENT_SUFFIX):
            base = node.value.id if isinstance(node.value, ast.Name) else None
            if base not in models_locals:
                names.add(node.attr)
    if _service_strings(tree):
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) \
                    and isinstance(node.value, str) \
                    and node.value.endswith(CLIENT_SUFFIX):
                names.add(node.value)
    return names


def _cos_imports(tree):
    """Return ``(name, error)`` pairs for the ``qcloud_cos`` imports in *tree*."""
    results = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or node.module != COS_PACKAGE:
            continue
        package, error = _import(COS_PACKAGE)
        if error:
            results.append((None, "SDK package %s does not exist (%s)"
                            % (COS_PACKAGE, error)))
            continue
        for alias in node.names:
            if not hasattr(package, alias.name):
                results.append((None, "%s does not define %s"
                                % (COS_PACKAGE, alias.name)))
    return results


def module_findings(root=REPO_ROOT):
    """Return a sorted list of unresolved SDK references in ``plugins/``."""
    findings = []
    parsed = []
    for relative, path in _plugin_sources(root):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as exc:
            findings.append("%s: cannot parse (%s)" % (relative, exc))
            continue
        parsed.append((relative, tree))

    # Every client module the plugin tree imports is a candidate owner for a
    # referenced client class: the hand-written modules reach their SDK
    # through module_utils helpers, so the class and its import often live in
    # different files.
    known_clients = {}
    for _relative, tree in parsed:
        _packages, clients = _sdk_imports(tree)
        for _local, package, submodule in clients:
            module, error = _import("%s.%s" % (package, submodule))
            if module is not None:
                known_clients[(package, submodule)] = module
    cos_module, _cos_error = _import(COS_PACKAGE)

    for relative, tree in parsed:
        packages, clients = _sdk_imports(tree)

        for package in sorted(packages):
            _module, error = _import(package)
            if error:
                findings.append("%s: SDK package %s does not exist (%s)"
                                % (relative, package, error))

        for _local, package, submodule in sorted(set(clients)):
            _module, error = _import("%s.%s" % (package, submodule))
            if error:
                findings.append(
                    "%s: SDK client module %s.%s does not exist (%s)"
                    % (relative, package, submodule, error))

        candidates = {key: module for key, module in known_clients.items()
                      if key[0] in packages}
        for key in _dynamic_clients(tree):
            module, _error = _import("%s.%s" % key)
            if module is not None:
                candidates[key] = module
        if _cos_imports(tree) and cos_module is not None:
            candidates[(COS_PACKAGE, COS_PACKAGE)] = cos_module

        for class_name in sorted(_client_class_references(tree)):
            if not candidates:
                continue  # no SDK binding in this file to verify against
            for module in candidates.values():
                if hasattr(module, class_name):
                    break
            else:
                findings.append(
                    "%s: SDK class %s is not defined by any of %s"
                    % (relative, class_name,
                       ", ".join(sorted("%s.%s" % key for key in candidates))))

        for _name, error in _cos_imports(tree):
            if error:
                findings.append("%s: %s" % (relative, error))

    return sorted(set(findings))


def spec_findings(root=REPO_ROOT):
    """Return a sorted list of unresolved SDK references in the auto specs."""
    specs_path = Path(root) / "scripts" / "info_specs_auto.py"
    if not specs_path.is_file():
        return ["scripts/info_specs_auto.py is missing"]
    spec = importlib.util.spec_from_file_location("info_specs_auto",
                                                  str(specs_path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    specs = getattr(module, "SPECS_AUTO", None)
    if not isinstance(specs, list) or not specs:
        return ["scripts/info_specs_auto.py must define a non-empty SPECS_AUTO"]

    findings = []
    for entry in specs:
        name = entry.get("module", "<unnamed>")
        package = entry.get("service_package")
        client_module = entry.get("client_module")
        if not package or not client_module:
            findings.append("%s: spec names no service package" % name)
            continue
        client, error = _import("%s.%s" % (package, client_module))
        if error:
            findings.append(
                "%s: spec names SDK client %s.%s, which does not exist (%s)"
                % (name, package, client_module, error))
            continue
        # The client class lives in the *_client module; the request models
        # live in the sibling ``models`` module.
        owners = (("client_class", "%s.%s" % (package, client_module),
                   client),
                  ("request_class", "%s.models" % package,
                   _import("%s.models" % package)[0]))
        for key, where, owner in owners:
            class_name = entry.get(key)
            if class_name and owner is not None and not hasattr(owner, class_name):
                findings.append("%s: spec names %s %s, which %s does not define"
                                % (name, key, class_name, where))
    return sorted(findings)


def collect_findings(root=REPO_ROOT, requirements=None):
    """Return ``(findings, notes)`` for the whole floor check."""
    findings = []
    notes = []
    requirements = Path(requirements) if requirements \
        else Path(root) / "requirements.txt"
    floor, cap = declared_range(requirements)
    if floor is None:
        findings.append("requirements.txt declares no readable lower bound for "
                        "tencentcloud-sdk-python")
    if cap is None:
        findings.append("requirements.txt declares no readable upper bound for "
                        "tencentcloud-sdk-python")
    try:
        installed = installed_version()
    except RuntimeError as exc:
        return [str(exc)], notes
    if floor and installed != floor:
        findings.append(
            "the declared SDK floor is %s but %s is installed: the floor is "
            "advertised, not verified. Install it "
            "(python -m pip install 'tencentcloud-sdk-python==%s') to verify "
            "it, or raise the floor to the release CI installs"
            % (floor, installed, floor))
    findings.extend(module_findings(root))
    findings.extend(spec_findings(root))
    notes.append("verified against tencentcloud-sdk-python %s" % installed)
    if floor:
        notes.append("declared floor %s, cap %s" % (floor, cap))
    return sorted(set(findings)), notes


def main(argv=None, out=None, err=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="exit 1 when a reference does not resolve at the "
                             "declared floor")
    parser.add_argument("--root", metavar="PATH", default=str(REPO_ROOT),
                        help="collection root to inspect (mainly for tests)")
    args = parser.parse_args(argv)
    out = out if out is not None else sys.stdout
    err = err if err is not None else sys.stderr

    findings, notes = collect_findings(root=args.root)
    for note in notes:
        print(note, file=out)
    if findings:
        print("findings (%d):" % len(findings), file=out)
        for finding in findings:
            print("  %s" % finding, file=out)
    if findings and args.check:
        print("every SDK reference must resolve at the declared floor: raise "
              "the floor in requirements.txt (and regenerate) or drop the "
              "reference", file=err)
        return 1
    if not findings:
        print("SDK floor check OK: every SDK reference resolves", file=out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
