#!/usr/bin/env python3
"""Lists every programme whose name cannot be linked to its own page.

The first pass of a refresh fills fees, dates and formats and often comes back
with whatever link it met first: a launch article, a course-listing site, the
school's calendar, a brochure. This audit is what the second pass works from.
It reads the catalogues and the launch register, judges each link from its URL
(scripts/linkkind.py; nothing is fetched here) and writes
outputs/link_queue.csv: one row per programme that has no programme page or
landing page on record, worst first.

The dashboard never links a programme's name to a news article, a listing
site, an index page or a short link. Until the second pass replaces one, the
name falls back to the brochure where there is one and is otherwise plain text.

Some schools publish no page per programme, only a calendar and a brochure.
When the second pass has looked and found that, it says so in
data/link_checks.csv (school_slug, programme_name, checked_on, finding) and the
programme stays out of the queue for RECHECK_DAYS, so the same dead ends are
not walked every week.
"""
import csv, glob, pathlib, collections, datetime
from linkkind import kind, FIX

RECHECK_DAYS = 90

ROOT = pathlib.Path(__file__).resolve().parent.parent
GROUP = {r['slug']: r['group'] for r in csv.DictReader(open(ROOT / 'data' / 'schools.csv', encoding='utf-8'))}
ORDER = {'ISB': 0, 'India': 1, 'Global': 2, 'Platform': 3}
# wrong links first, then missing ones, then programmes that only have a brochure
SEVERITY = {'news': 0, 'aggregator': 0, 'shortener': 0, 'private': 0, 'broken': 0, 'index': 1, 'none': 2, 'brochure': 3}

cat = [r for f in sorted(glob.glob(str(ROOT / 'data' / 'catalogues' / '*.csv')))
       for r in csv.DictReader(open(f, encoding='utf-8'))]
shared = collections.Counter(r['url'].strip() for r in cat if (r.get('url') or '').strip())


def url_kind(r):
    """a link several programmes share is an index, whatever its address looks like"""
    u = (r.get('url') or '').strip()
    k = kind(u)
    return 'index' if k == 'page' and shared[u] >= 3 else k


checked = {}
_lc = ROOT / 'data' / 'link_checks.csv'
if _lc.exists():
    for r in csv.DictReader(open(_lc, encoding='utf-8')):
        try:
            age = (datetime.date.today() - datetime.date.fromisoformat(r['checked_on'][:10])).days
        except ValueError:
            continue
        if age <= RECHECK_DAYS:
            checked[(r['school_slug'], r['programme_name'].strip().lower())] = r['checked_on']
skipped = 0

rows = []
for r in cat:
    if (r.get('status') or '').strip():          # likely discontinued: its page is the thing that is gone
        continue
    if (r['school_slug'], r['programme_name'].strip().lower()) in checked:
        skipped += kind(r.get('landing_url')) != 'page' and url_kind(r) != 'page'
        continue
    lk, uk = kind(r.get('landing_url')), url_kind(r)
    if lk == 'page' or uk == 'page':
        continue
    bu = (r.get('brochure_url') or '').strip()
    has_brochure = kind(bu) in ('brochure', 'page') or uk == 'brochure'
    k = uk if uk != 'brochure' or lk == 'none' else lk
    rows.append(dict(
        severity=SEVERITY.get(k, 2), priority=ORDER.get(GROUP.get(r['school_slug']), 9),
        where='catalogue', file=f"data/catalogues/{r['school_slug']}.csv", school_slug=r['school_slug'],
        programme_name=r['programme_name'], field='url', current=(r.get('url') or '').strip(), kind=k,
        problem=FIX[k], shown_meanwhile='brochure' if has_brochure else 'no link',
        fix='find the programme page at the school or its delivery partner and write it to url'
            + ('; move the PDF to brochure_url' if uk == 'brochure' and not bu else '')))

reg = ROOT / 'data' / 'peer_launches.csv'
if reg.exists():
    held = {(r['school_slug'], r['programme_name'].strip().lower()) for r in cat
            if kind(r.get('landing_url')) == 'page' or url_kind(r) == 'page'}
    for r in csv.DictReader(open(reg, encoding='utf-8')):
        k = kind(r.get('url'))
        if k == 'page' or (r['school_slug'], r['programme'].strip().lower()) in held:
            continue
        if (r['school_slug'], r['programme'].strip().lower()) in checked:
            skipped += 1
            continue
        if k == 'none' and kind(r.get('source_url')) != 'none':
            k = kind(r.get('source_url'))       # only the launch article is held
        rows.append(dict(
            severity=SEVERITY.get(k, 2), priority=ORDER.get(GROUP.get(r['school_slug']), 9),
            where='launch register', file='data/peer_launches.csv', school_slug=r['school_slug'],
            programme_name=r['programme'], field='url',
            current=(r.get('url') or r.get('source_url') or '').strip(), kind=k,
            problem=FIX[k], shown_meanwhile='brochure' if k == 'brochure' else 'no link',
            fix='write the programme page to url; keep the article or brochure in source_url as the evidence'))

rows.sort(key=lambda x: (x['severity'], x['priority'], x['school_slug'], x['programme_name']))
out = ROOT / 'outputs' / 'link_queue.csv'
cols = ['where', 'file', 'school_slug', 'programme_name', 'field', 'current', 'kind', 'problem', 'shown_meanwhile', 'fix']
with open(out, 'w', newline='', encoding='utf-8') as fh:
    w = csv.DictWriter(fh, fieldnames=cols, quoting=csv.QUOTE_ALL, extrasaction='ignore')
    w.writeheader()
    w.writerows(rows)
c = collections.Counter(r['kind'] for r in rows)
print(f'link queue: {len(rows)} programmes without a programme or landing page; by what they hold now: {dict(c)}'
      + (f'; {skipped} more were checked in the last {RECHECK_DAYS} days and have no page to find' if skipped else ''))
