"""Triage SLA report: how fast do we actually answer?

The maintainer docs promise a first response on issues and pull requests
within 48 hours (see docs/triage.md). A promise nobody measures is a
promise nobody keeps, and GitHub has no built-in "first response time"
metric, so this script computes it from the API and prints it.

First response means the first comment by somebody other than the author,
or, for a pull request, the first submitted review (a reviewer who leaves
only a review has still responded). Comments by bots are ignored, because
dependabot and the changelog bot answer instantly and would make every
number look perfect.

Usage:
    python scripts/triage_sla.py                 # open issues and PRs
    python scripts/triage_sla.py --closed 30     # also the last 30 days
    python scripts/triage_sla.py --json          # machine-readable
    python scripts/triage_sla.py --check         # exit 1 on any breach

Authentication is optional but recommended: unauthenticated requests are
rate-limited to 60/hour. The token is read from GITHUB_TOKEN or GH_TOKEN,
falling back to `gh auth token`.
"""
import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

API = 'https://api.github.com'
SLA_HOURS = 48.0
BOT_SUFFIX = '[bot]'


class GitHub:
    def __init__(self, repo, token):
        self.repo = repo
        self.token = token

    def get(self, path, **params):
        url = '%s/repos/%s/%s' % (API, self.repo, path.lstrip('/'))
        if params:
            url += '?' + urllib.parse.urlencode(params)
        while url:
            request = urllib.request.Request(url)
            request.add_header('Accept', 'application/vnd.github+json')
            if self.token:
                request.add_header('Authorization', 'Bearer ' + self.token)
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    yield from json.load(response)
                    url = self._next(response.headers.get('Link'))
            except urllib.error.HTTPError as exc:
                raise SystemExit('GitHub API error %s for %s' % (exc.code, url)) from exc

    @staticmethod
    def _next(link):
        if not link:
            return None
        for part in link.split(','):
            if 'rel="next"' in part and '<' in part:
                return part[part.index('<') + 1:part.index('>')]
        return None


def token():
    for name in ('GITHUB_TOKEN', 'GH_TOKEN'):
        if os.environ.get(name):
            return os.environ[name]
    try:
        return subprocess.run(
            ['gh', 'auth', 'token'],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ''


def repo_from_remote():
    try:
        url = subprocess.run(
            ['git', 'remote', 'get-url', 'origin'],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ''
    if url.startswith('git@'):
        url = url.replace(':', '/', 1).replace('git@', 'https://')
    path = url.split('github.com/', 1)[-1]
    return path[:-4] if path.endswith('.git') else path


def parsed(value):
    return datetime.strptime(value, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)


def first_response(client, item, author):
    """Earliest non-author, non-bot response, in hours, or None."""
    number = item['number']
    stamps = []
    if item.get('pull_request'):
        for review in client.get('pulls/%d/reviews' % number, per_page=100):
            if review['user']['login'] != author:
                stamps.append(parsed(review['submitted_at']))
    for comment in client.get('issues/%d/comments' % number, per_page=100):
        user = comment['user']['login']
        if user != author and not user.endswith(BOT_SUFFIX):
            stamps.append(parsed(comment['created_at']))
    if not stamps:
        return None
    return min((stamp - parsed(item['created_at'])).total_seconds() / 3600.0 for stamp in stamps)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--repo', default=repo_from_remote(),
                        help='owner/name (default: from the origin remote)')
    parser.add_argument('--closed', type=int, metavar='DAYS', default=0,
                        help='also report items closed in the last N days')
    parser.add_argument('--sla', type=float, default=SLA_HOURS,
                        help='first-response SLA in hours (default: 48)')
    parser.add_argument('--json', action='store_true', help='print JSON instead of a table')
    parser.add_argument('--check', action='store_true',
                        help='exit 1 if any open item has breached the SLA')
    args = parser.parse_args()
    if not args.repo:
        raise SystemExit('no --repo given and the origin remote is not on GitHub')

    client = GitHub(args.repo, token())
    now = datetime.now(timezone.utc)
    rows = []
    for item in client.get('issues', state='open', per_page=100, sort='created', direction='asc'):
        rows.append(describe(client, item, now, args.sla, 'open'))
    if args.closed:
        since = (now - timedelta(days=args.closed)).strftime('%Y-%m-%dT%H:%M:%SZ')
        for item in client.get('issues', state='closed', per_page=100, since=since,
                               sort='updated', direction='desc'):
            rows.append(describe(client, item, now, args.sla, 'closed'))

    if args.json:
        print(json.dumps(rows, indent=2))
    else:
        report(rows, args)
    if args.check and any(row['status'] == 'BREACH' for row in rows):
        sys.exit(1)


def describe(client, item, now, sla, state):
    author = item['user']['login']
    created = parsed(item['created_at'])
    age = (now - created).total_seconds() / 3600.0
    response = first_response(client, item, author)
    if response is None:
        status = 'BREACH' if age > sla else 'WAITING'
    else:
        status = 'OK' if response <= sla else 'BREACH'
    return {
        'kind': 'pr' if item.get('pull_request') else 'issue',
        'number': item['number'],
        'title': item['title'],
        'author': author,
        'state': state,
        'age_hours': round(age, 1),
        'response_hours': None if response is None else round(response, 1),
        'status': status,
    }


def report(rows, args):
    print('Triage SLA for %s — first response within %.0fh\n' % (args.repo, args.sla))
    print('%-5s %-6s %8s %11s  %-8s %s' % ('KIND', 'NUMBER', 'AGE(h)', 'RESPONSE(h)', 'STATUS', 'TITLE'))
    for row in sorted(rows, key=lambda r: (r['kind'], r['number'])):
        print('%-5s %-6s %8.1f %11s  %-8s %s' % (
            row['kind'], '#' + str(row['number']), row['age_hours'],
            '—' if row['response_hours'] is None else '%.1f' % row['response_hours'],
            row['status'], row['title'][:58],
        ))
    answered = [row for row in rows if row['response_hours'] is not None]
    met = [row for row in answered if row['response_hours'] <= args.sla]
    print('\n%d item(s), %d answered' % (len(rows), len(answered)))
    if answered:
        print('%d/%d answered within the SLA (%.0f%%)' % (
            len(met), len(answered), 100.0 * len(met) / len(answered)))
    breaches = [row for row in rows if row['status'] == 'BREACH']
    if breaches:
        print('breached: %s' % ', '.join('#%d' % row['number'] for row in breaches))


if __name__ == '__main__':
    main()
