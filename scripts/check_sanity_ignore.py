"""Sanity-ignore budget guard.

ansible-test sanity failures are progressively triaged (see docs/product-depth.md
and the ignore-*.txt family breakdown below). This guard keeps the TOTAL number
of ignore lines from silently growing between releases: raising the budget is a
deliberate act (update BASELINE_TOTAL with a comment) instead of an accident of
new generated modules.

Usage: python scripts/check_sanity_ignore.py [--print]
"""
import glob
import os
import sys
import collections

BASELINE_TOTAL = 2350  # current committed total (2026-09-10): 2289 + headroom
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    counts = collections.Counter()
    total = 0
    for path in glob.glob(os.path.join(ROOT, 'tests', 'sanity', 'ignore-*.txt')):
        with open(path, encoding='utf-8') as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                parts = line.split()
                if len(parts) >= 2:
                    counts[parts[1]] += 1
                total += 1
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
