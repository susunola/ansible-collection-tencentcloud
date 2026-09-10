"""Sanity-ignore budget guard.

ansible-test sanity failures are progressively triaged (see docs/product-depth.md
and the ignore-*.txt family breakdown below). This guard keeps the TOTAL number
of ignore lines from silently growing between releases: raising the budget is a
deliberate act (update BASELINE_TOTAL with a comment) instead of an accident of
new generated modules.

It also rejects entries that point at a file that no longer exists. An ignore
line naming a deleted file is not "an ignore we might still need", it is a
failure of ansible-test's own ``ignores`` test -- one that lands as hundreds of
lines of "File ... does not exist" and, because it is easy to mistake for noise,
kept ``main`` red for a day. Every entry names a real file or the guard fails.

Usage: python scripts/check_sanity_ignore.py [--print]
"""
import glob
import os
import sys
import collections

BASELINE_TOTAL = 1900  # current committed total (2026-09-10): 1557 + headroom
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    counts = collections.Counter()
    total = 0
    missing = []
    for path in glob.glob(os.path.join(ROOT, 'tests', 'sanity', 'ignore-*.txt')):
        with open(path, encoding='utf-8') as fh:
            for number, line in enumerate(fh, start=1):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                parts = line.split()
                if len(parts) >= 2:
                    counts[parts[1]] += 1
                total += 1
                if not os.path.exists(os.path.join(ROOT, parts[0])):
                    missing.append('%s:%d: %s' % (
                        os.path.relpath(path, ROOT), number, parts[0]))
    if missing:
        print('FAIL: %d ignore entries name a file that does not exist; '
              'drop them (they break ansible-test sanity "ignores"):' % len(missing),
              file=sys.stderr)
        for entry in missing:
            print('  %s' % entry, file=sys.stderr)
        sys.exit(1)
    if '--print' in sys.argv:
        for code, n in counts.most_common(14):
            print(f'{n:5} {code}')
        print(f'TOTAL {total}')
    if total > BASELINE_TOTAL:
        print(f'FAIL: sanity ignore total {total} exceeds budget {BASELINE_TOTAL}; '
              'triage ignores (see docs/product-depth.md) or raise the budget deliberately.',
              file=sys.stderr)
        sys.exit(1)
    print(f'ok: sanity ignore total {total} within budget {BASELINE_TOTAL}')
    sys.exit(0)


if __name__ == '__main__':
    main()
