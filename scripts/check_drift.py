#!/usr/bin/env python3
"""Fails the build if a school's product count moved more than 10% since the last
snapshot. A silent scraper breakage must not quietly rewrite the numbers."""
import csv, json, collections, pathlib, sys, datetime
ROOT=pathlib.Path(__file__).resolve().parent.parent
cur=collections.Counter(r['school_slug'] for r in csv.DictReader(
    open(ROOT/'programmes_tagged.csv',encoding='utf-8')))
snapdir=ROOT/'snapshots'; snapdir.mkdir(exist_ok=True)
prev=sorted(snapdir.glob('*.json'))
today=datetime.date.today().strftime('%Y-%m')
(snapdir/f'{today}.json').write_text(json.dumps(dict(cur),indent=1))
if not prev:
    print('no prior snapshot; baseline written'); sys.exit(0)
old=json.loads(prev[-1].read_text())
bad=[]
for s,n in old.items():
    now=cur.get(s,0)
    if n and abs(now-n)/n > 0.10: bad.append(f'{s}: {n} -> {now}')
if bad:
    print('DRIFT over 10%:'); [print('  '+b) for b in bad]
    print('Review the capture before publishing. Re-run once explained.')
    sys.exit(1)
print('drift check passed vs', prev[-1].name)
