#!/usr/bin/env python3
"""One-off: rebuilds data/history/ from the repository's own history.

Run once, on 18 Nov 2026, when the change history began. The starting point is
the catalogue as it stood after the team's competitor sheet was merged in on
30 Sep 2026 (commit cc515ad). Every later commit that touched data/catalogues
is compared with the one before, in order, and each change is dated by its
commit. The weekly re-check had not started then, so every replaced value is
ours (a first check against a live page, or a correction), not the school's.

Needs the full history: run in a clone, not a shallow checkout.
"""
import csv, io, subprocess, pathlib, sys

R = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / 'scripts'))
import what_changed as wc  # noqa: E402

BASE = 'cc515ad'


def git(*a):
    return subprocess.run(['git', *a], cwd=R, capture_output=True, text=True, check=True).stdout


def rows_at(rev):
    files = [f for f in git('ls-tree', '--name-only', rev, 'data/catalogues/').split() if f.endswith('.csv')]
    return [r for f in sorted(files) for r in csv.DictReader(io.StringIO(git('show', f'{rev}:{f}')))]


commits = git('log', '--reverse', '--format=%h %ad', '--date=short', f'{BASE}..HEAD', '--', 'data/catalogues').split('\n')
commits = [c.split() for c in commits if c.strip()]
prev = wc.state_of(rows_at(BASE))
events = []
for sha, date in commits:
    cur = wc.state_of(rows_at(sha))
    ev = wc.diff(prev, cur, date)
    for e in ev:
        e['note'] = (e['note'] + '; ' if e['note'] else '') + f'commit {sha}'
    events += ev
    print(f'{sha} {date}: {len(ev)} changes')
    prev = cur

# the working tree must match the last commit; anything newer is the next run's
now = wc.state_of(wc.catalogue_rows())
if now != prev:
    sys.exit('catalogues differ from the last commit: commit them first, then backfill')
wc.append_log(events, fresh=True)
wc.write_state(now)
print(f'{len(events)} changes from {wc.HISTORY_START} written to data/history/changes.csv')
