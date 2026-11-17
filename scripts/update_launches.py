#!/usr/bin/env python3
"""Keeps the launch register up to date without anyone editing it by hand.

The Product Team compiled the register once. From then on, every build adds a
programme to data/peer_launches.csv when it appears in a school's catalogue for
the first time (it is in no earlier snapshot) and its own page marks it new
(is_new_2025_26 = Y, set by the weekly refresh). It is dated by the day it was
first seen, marked probable until someone confirms an announcement date, and
never added twice. The register's window then rolls: as of today, back 12 months.
A programme that is new to our tracking but not marked new on its page is not a
launch: it is counted in the catalogue, not in New launches.
"""
import csv, glob, json, pathlib, re, datetime

ROOT = pathlib.Path(__file__).resolve().parent.parent
TODAY = datetime.date.today()
REG, META = ROOT / 'data' / 'peer_launches.csv', ROOT / 'data' / 'peer_launches_meta.json'
norm = lambda s: ' '.join(re.sub(r'[^a-z0-9 ]', ' ', re.sub(r'\(.*?\)|\[.*?\]|batch[\s-]*\d+', ' ', (s or '').lower())).split())

seen = set()
for f in (ROOT / 'snapshots').glob('programmes-*.csv'):
    seen |= {(r['school_slug'], r['programme_name']) for r in csv.DictReader(open(f, encoding='utf-8'))}
reg = list(csv.DictReader(open(REG, encoding='utf-8', newline='')))
cols = list(reg[0].keys())
held = {(r['school_slug'], norm(r['programme'])) for r in reg}
added = []
if seen:  # with no earlier snapshot there is nothing to compare against
    for f in sorted(glob.glob(str(ROOT / 'data' / 'catalogues' / '*.csv'))):
        for r in csv.DictReader(open(f, encoding='utf-8')):
            k = (r['school_slug'], r['programme_name'])
            if r['school_slug'] == 'isb' or k in seen or (r['school_slug'], norm(r['programme_name'])) in held:
                continue
            if not (r.get('is_new_2025_26') or '').strip().upper().startswith('Y'):
                continue
            row = dict.fromkeys(cols, '')
            row.update(school_slug=r['school_slug'], programme=r['programme_name'], launch_date=TODAY.isoformat(),
                       evidence=f'First seen in the school\'s catalogue on {TODAY:%d %b %Y}; its page marks it new',
                       first_cohort=r.get('next_start', ''), format=r.get('format', ''), duration=r.get('duration_raw', ''),
                       fee=r.get('fee_raw', ''), partner=r.get('partner', ''),
                       url=(r.get('landing_url') or r.get('url') or '').strip(), probable='Y')
            reg.append(row); held.add((r['school_slug'], norm(r['programme_name']))); added.append(row['programme'])
if added:
    with open(REG, 'w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=cols, quoting=csv.QUOTE_ALL, lineterminator='\n'); w.writeheader(); w.writerows(reg)
meta = json.loads(META.read_text(encoding='utf-8'))
meta['asof'], meta['from'] = TODAY.isoformat(), (TODAY - datetime.timedelta(days=365)).isoformat()
META.write_text(json.dumps(meta, indent=1, ensure_ascii=False), encoding='utf-8')
print(f'launch register: {len(added)} added from catalogues; window {meta["from"]} to {meta["asof"]}' + (f': {added}' if added else ''))
