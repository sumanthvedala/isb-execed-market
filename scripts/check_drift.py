#!/usr/bin/env python3
"""Fails the build if a school's product count moved more than 10% since the last
snapshot. A silent scraper breakage must not quietly rewrite the numbers."""
import csv, json, collections, pathlib, sys, datetime
ROOT=pathlib.Path(__file__).resolve().parent.parent
cur=collections.Counter(r['school_slug'] for r in csv.DictReader(
    open(ROOT/'programmes_tagged.csv',encoding='utf-8')))
snapdir=ROOT/'snapshots'; snapdir.mkdir(exist_ok=True)
today=datetime.date.today().strftime('%Y-%m')
# compare against the latest snapshot from an EARLIER month. Reading it after
# writing this month's file compared the run with itself and always passed.
prev=[p for p in sorted(snapdir.glob('20??-??.json')) if p.stem<today]
old=json.loads(prev[-1].read_text()) if prev else {}
(snapdir/f'{today}.json').write_text(json.dumps(dict(cur),indent=1))
# programme-level snapshot: next month's build diffs against it to show what
# peers added, dropped or repriced (build_data.py reads these)
with open(snapdir/f'programmes-{today}.csv','w',newline='',encoding='utf-8') as f:
    w=csv.writer(f,quoting=csv.QUOTE_ALL); w.writerow(['school_slug','programme_name','topic_id','format','fee_currency','fee_amount'])
    for r in csv.DictReader(open(ROOT/'programmes_tagged.csv',encoding='utf-8')):
        w.writerow([r['school_slug'],r['programme_name'],r['topic_id'],r['format'],r['fee_currency'],r['fee_amount']])
if not prev:
    print('no prior snapshot; baseline written'); sys.exit(0)
# a deliberate re-scope (new schools, a merged sheet) is not a scraper failure
ACCEPT=set(filter(None,(ROOT/'snapshots'/'ACCEPT_DRIFT').read_text().split())) \
    if (ROOT/'snapshots'/'ACCEPT_DRIFT').exists() else set()
bad=[]
for s,n in old.items():
    if s in ACCEPT: continue
    now=cur.get(s,0)
    if n and abs(now-n)/n > 0.10: bad.append(f'{s}: {n} -> {now}')
if bad:
    print('DRIFT over 10%:'); [print('  '+b) for b in bad]
    print('Review the capture before publishing. Re-run once explained.')
    sys.exit(1)
print('drift check passed vs', prev[-1].name)
