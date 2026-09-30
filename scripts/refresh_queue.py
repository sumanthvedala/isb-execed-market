#!/usr/bin/env python3
"""Lists what the monthly refresh must fetch, and nothing else.

Writes outputs/refresh_queue.csv: one row per catalogue programme with a missing
core field, a lapsed start date, or a team-sheet origin that no live page has
confirmed yet. The scheduled Claude refresh (data/REFRESH_SPEC.md) works through
this file top to bottom and writes answers back into data/catalogues/*.csv.
"""
import csv, glob, datetime, pathlib, collections

ROOT = pathlib.Path(__file__).resolve().parent.parent
TODAY = datetime.date.today()
GROUP = {r['slug']: r['group'] for r in csv.DictReader(open(ROOT / 'data' / 'schools.csv', encoding='utf-8'))}
ORDER = {'ISB': 0, 'India': 1, 'Global': 2, 'Platform': 3}
STALE_DAYS = 120          # re-check anything not confirmed on a live page in four months

rows = []
for f in sorted(glob.glob(str(ROOT / 'data' / 'catalogues' / '*.csv'))):
    for r in csv.DictReader(open(f, encoding='utf-8')):
        need = []
        if not (r.get('fee_amount') or '').strip():
            need.append('fee')
        if (r.get('format') or 'Unknown') == 'Unknown':
            need.append('format')
        if not (r.get('duration_weeks') or r.get('duration_days') or '').strip():
            need.append('duration')
        if not (r.get('next_start') or '').strip():
            need.append('next_start')
        why = []
        if r.get('provenance') == 'team-sheet' and not r.get('last_verified'):
            why.append('added from team sheet; confirm it is still sold')
        lv = (r.get('last_verified') or '')[:10]
        try:
            if (TODAY - datetime.date.fromisoformat(lv)).days > STALE_DAYS:
                why.append(f'last verified {lv}')
        except ValueError:
            pass
        if need or why:
            rows.append(dict(priority=ORDER.get(GROUP.get(r['school_slug']), 9), school_slug=r['school_slug'],
                             programme_name=r['programme_name'], url=r.get('url', ''),
                             fetch=';'.join(need), reason='; '.join(why) or 'missing fields'))
rows.sort(key=lambda x: (x['priority'], x['school_slug'], -len(x['fetch'].split(';')), x['programme_name']))
out = ROOT / 'outputs' / 'refresh_queue.csv'
with open(out, 'w', newline='', encoding='utf-8') as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()) if rows else ['priority'], quoting=csv.QUOTE_ALL)
    w.writeheader()
    w.writerows(rows)
c = collections.Counter(f for r in rows for f in r['fetch'].split(';') if f)
print(f'refresh queue: {len(rows)} programmes; fields missing: {dict(c)}')
