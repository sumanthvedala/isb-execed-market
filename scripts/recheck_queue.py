#!/usr/bin/env python3
"""This week's re-check list: half of all programmes, so each is re-read every two weeks.

Pass 3 of the weekly refresh (data/REFRESH_SPEC.md) re-reads the page of every
programme on this list and records what it found in data/recheck_log.csv. That
log is how scripts/what_changed.py tells a school's change (a fee raised, a
module added) from a correction to our own record.

Order: programmes never re-checked first, then the longest since their last
re-check. Within that, IIM Ahmedabad, Bangalore, Calcutta, Indore, Kozhikode and
Lucknow, then the global schools in alphabetical order, then SP Jain, then ISB
and the platforms. A row the session did not reach stays at the top next week.

Writes outputs/recheck_queue.csv.
"""
import csv, glob, math, pathlib

R = pathlib.Path(__file__).resolve().parent.parent
schools = {r['slug']: r for r in csv.DictReader(open(R / 'data' / 'schools.csv', encoding='utf-8'))}
iims = sorted((s for s in schools if s.startswith('iim')), key=lambda s: schools[s]['school'])
glob_ = sorted((s for s in schools if schools[s]['group'] == 'Global'), key=lambda s: schools[s]['school'])
rest = ['spjain', 'isb'] + sorted(s for s in schools if schools[s]['group'] == 'Platform')
ORDER = {s: i for i, s in enumerate(iims + glob_ + [s for s in rest if s in schools])}

last = {}
p = R / 'data' / 'recheck_log.csv'
if p.exists():
    for r in csv.DictReader(open(p, encoding='utf-8')):
        k = (r['school_slug'], r['programme_name'].strip())
        last[k] = max(last.get(k, ''), (r.get('checked_on') or '')[:10])

rows = []
for f in glob.glob(str(R / 'data' / 'catalogues' / '*.csv')):
    for n, r in enumerate(csv.DictReader(open(f, encoding='utf-8'))):
        if not (r.get('programme_name') or '').strip() or r['school_slug'] not in ORDER:
            continue
        k = (r['school_slug'], r['programme_name'].strip())
        rows.append((last.get(k, ''), ORDER[r['school_slug']], n, r))
rows.sort(key=lambda x: x[:3])
take = rows[:math.ceil(len(rows) / 2)]

cols = ['school_slug', 'programme_name', 'page', 'last_rechecked', 'fee_raw', 'fee_currency', 'fee_amount',
        'duration_raw', 'total_modules', 'format', 'next_start', 'status']
with open(R / 'outputs' / 'recheck_queue.csv', 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f, quoting=csv.QUOTE_ALL, lineterminator='\n')
    w.writerow(cols)
    for lc, _, _, r in take:
        page = next((r.get(c) for c in ('landing_url', 'url', 'brochure_url') if (r.get(c) or '').strip()), '')
        w.writerow([r['school_slug'], r['programme_name'], page, lc] + [r.get(c, '') for c in cols[4:]])

by = {}
for _, _, _, r in take:
    by[r['school_slug']] = by.get(r['school_slug'], 0) + 1
print(f"re-check queue: {len(take)} of {len(rows)} programmes this week -> outputs/recheck_queue.csv; "
      + ', '.join(f'{s} {n}' for s, n in sorted(by.items(), key=lambda x: ORDER[x[0]])))
