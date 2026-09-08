"""Depth backlog helper (offline).

Lists, per product, write modules that have no sibling ``_info`` yet and
whether each is already tracked in the curated KNOWN_GAPS backlog of
scripts/audit_info_coverage.py.

Usage: python scripts/gap_backlog.py [--all]
"""
import collections
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOD = os.path.join(ROOT, 'plugins', 'modules')
AUDIT = os.path.join(ROOT, 'scripts', 'audit_info_coverage.py')


def module_names():
    return {f[:-3] for f in os.listdir(MOD) if f.endswith('.py') and not f.startswith('__')}


def known_gaps():
    with open(AUDIT, encoding='utf-8') as fh:
        src = fh.read()
    m = re.search(r'KNOWN_GAPS\s*=\s*\{', src)
    if not m:
        return set()
    start = m.end()
    depth = 0
    i = start
    while i < len(src):
        if src[i] == '{':
            depth += 1
        elif src[i] == '}':
            depth -= 1
            if depth == 0:
                break
        i += 1
    body = src[start:i]
    names = re.findall(r'"([a-z][a-z0-9_]+)"', body)
    return set(names)


def main():
    all_flag = '--all' in sys.argv
    names = module_names()
    res = [n for n in names if not n.endswith('_info')]
    gaps = known_gaps()
    missing = collections.defaultdict(list)
    for m in res:
        if m + '_info' not in names:
            missing[m.split('_', 1)[0]].append(m)
    total = 0
    for prod in sorted(missing):
        items = missing[prod]
        if not all_flag and len(items) > 12:
            shown = items[:8] + ['...']
        else:
            shown = items
        untracked = [m for m in items if m not in gaps]
        total += len(items)
        print(f'## {prod}: {len(items)} missing sibling _info ({len(items) - len(untracked)} in KNOWN_GAPS, {len(untracked)} UNTRACKED)')
        if not all_flag and len(items) > 12:
            pass
        for m in shown:
            mark = 'gap' if m in gaps else 'UNTRACKED'
            print(f'   [{mark}] {m}')
        print()
    print(f'products={len(missing)} total_missing_siblings={total}')
    sys.exit(0)


if __name__ == '__main__':
    main()
