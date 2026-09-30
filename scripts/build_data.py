#!/usr/bin/env python3
"""Builds site/data.json from the analysis outputs. Run after analyse.py and
demand_index.py. Keeping this separate from the page means a refresh rewrites
one JSON file and the HTML diff stays empty."""
import csv, json, glob, collections, pathlib, datetime, re
R = pathlib.Path(__file__).resolve().parent.parent
L = lambda p: list(csv.DictReader(open(R / p, encoding='utf-8')))
num = lambda v: float(v) if re.fullmatch(r'\d+(\.\d+)?', (v or '').strip()) else None

schools = L('data/schools.csv')
S = [s['slug'] for s in schools]
fx = {r['currency']: float(r['inr_per_unit']) for r in L('data/fx.csv')}
prog = L('programmes_tagged.csv'); tax = L('data/taxonomy.csv')
tp = {r['topic_id']: r for r in L('outputs/matrix_topic_full.csv')}
gap = {r['topic_id']: r for r in L('outputs/gap_register.csv')}
di = {r['topic_id']: r for r in L('outputs/demand_index.csv')}

# the richer per-programme fields live in the catalogues, keyed by school + name
raw = {}
for f in glob.glob(str(R / 'data/catalogues/*.csv')):
    for r in csv.DictReader(open(f, encoding='utf-8')):
        raw.setdefault((r['school_slug'], r['programme_name'].strip()), r)
clip = lambda s, n: (s[:n] + '…') if len(s) > n else s


def g(p, k):
    return ((raw.get((p['school_slug'], p['programme_name'].strip())) or {}).get(k, '') or '').strip()


def inr(p):
    a, c = num(p['fee_amount']), p['fee_currency']
    return round(a * fx[c]) if a and c in fx else None


def weeks(p):
    w, d = num(p['duration_weeks']), num(p['duration_days'])
    return w if w else (round(d / 5, 1) if d else None)


progs = []
for p in prog:
    if p['theme'] == 'UNCLASSIFIED':
        continue
    progs.append({
        'sc': p['school_slug'], 'n': p['programme_name'], 't': p['topic_id'], 'sec': p['secondary_topic_id'],
        'f': p['format'].split(';')[0].strip() or 'Unknown', 'lv': p['level'] or 'Unknown',
        'w': weeks(p), 'dr': clip(g(p, 'duration_raw'), 50),
        'inr': inr(p), 'fr': clip(g(p, 'fee_raw'), 46),
        'pt': p['partner'], 'nw': 1 if (p['is_new'] or '').upper().startswith('Y') else 0,
        'ns': g(p, 'next_start')[:10], 'ls': g(p, 'last_known_start')[:10],
        'cap': g(p, 'capstone'), 'imm': g(p, 'campus_immersion'), 'iv': g(p, 'industry_visit'),
        'ta': clip(g(p, 'target_audience'), 200), 'kt': clip(g(p, 'key_topics'), 300),
        'u': p['url'], 'conf': p['match_confidence'], 'cat': clip(p['school_category'], 100),
        'prov': g(p, 'provenance'), 'lvf': g(p, 'last_verified')[:10], 'runs': int(p['scheduled_runs'] or 1)})

topics = []
for t in tax:
    m, c, d = tp.get(t['topic_id'], {}), gap.get(t['topic_id'], {}), di.get(t['topic_id'], {})
    topics.append({
        'id': t['topic_id'], 'n': t['topic'], 'th': t['theme'], 'st': t['subtheme'], 'ai': t['ai_era_flag'],
        'dem': int(m.get('demand_score') or 0), 'srcs': int(m.get('demand_sources') or 0),
        'geo': m.get('demand_geographies', ''), 'dsl': clip(m.get('demand_source_list', ''), 400),
        'idx': int(d.get('demand_index') or 0), 'out': int(d['outlook_2027_31']) if d.get('outlook_2027_31') else None,
        'why2': d.get('outlook_rationale', ''), 'sig': d.get('best_signal', ''),
        'isb': int(m.get('isb') or 0), 'peers': int(m.get('peers_present') or 0),
        'resid': m.get('supply_is_residual_bucket') == 'Y',
        'call': c.get('call', ''), 'why': c.get('why', '')})

# programme-level change since the latest snapshot from an earlier month
this_month = datetime.date.today().strftime('%Y-%m')
snaps = [p for p in sorted((R / 'snapshots').glob('programmes-*.csv')) if p.stem[-7:] < this_month]
changes = None
if snaps:
    old = {(r['school_slug'], r['programme_name']): r for r in csv.DictReader(open(snaps[-1], encoding='utf-8'))}
    cur = {(p['school_slug'], p['programme_name']): p for p in prog}
    changes = {'since': snaps[-1].stem[-7:],
               'added': [[s, n, cur[(s, n)]['topic_id']] for (s, n) in cur.keys() - old.keys()],
               'dropped': [[s, n, old[(s, n)]['topic_id']] for (s, n) in old.keys() - cur.keys()],
               'repriced': [[s, n, old[(s, n)]['fee_amount'], cur[(s, n)]['fee_amount']]
                            for (s, n) in cur.keys() & old.keys()
                            if old[(s, n)]['fee_amount'] and cur[(s, n)]['fee_amount']
                            and old[(s, n)]['fee_amount'] != cur[(s, n)]['fee_amount']]}

q = L('outputs/refresh_queue.csv') if (R / 'outputs/refresh_queue.csv').exists() else []
d = {'asof': datetime.date.today().strftime('%d %b %Y'),
     'schools': [{'s': s['slug'], 'l': s['label'], 'g': s['group'], 'n': s['school']} for s in schools],
     'themes': list(dict.fromkeys(t['theme'] for t in tax)),
     'topics': topics, 'progs': progs, 'changes': changes,
     'fx': {k: v for k, v in fx.items() if k != 'INR'}, 'fxDate': L('data/fx.csv')[0]['set_on'],
     'quality': {'queue': len(q), 'noFee': sum(1 for p in progs if p['inr'] is None),
                 'noStart': sum(1 for p in progs if not p['ns']),
                 'fromSheet': sum(1 for p in progs if p['prov'] == 'team-sheet'),
                 'signals': len(L('data/demand_all.csv'))}}
(R / 'site' / 'data.json').write_text(json.dumps(d, separators=(',', ':'), ensure_ascii=False), encoding='utf-8')
print('site/data.json written:', len(json.dumps(d)), 'bytes;', len(progs), 'programmes')
