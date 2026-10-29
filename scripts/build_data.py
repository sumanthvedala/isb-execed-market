#!/usr/bin/env python3
"""Builds site/data.json from the analysis outputs. Run after analyse.py and
demand_index.py. Keeping this separate from the page means a refresh rewrites
one JSON file and the HTML diff stays empty."""
import csv, json, glob, collections, pathlib, datetime, re, urllib.parse
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


_shared = collections.Counter(p['url'].strip() for p in prog)


def specific(u):
    """a link that names one programme, not a school's home page, catalogue
    index or calendar; a URL several programmes share is an index too"""
    u = (u or '').strip()
    if not u.startswith('http') or _shared[u] >= 3:
        return ''
    path = urllib.parse.urlparse(u).path.strip('/').lower()
    if path in ('', 'index.php', 'index.html', 'en', 'programmes', 'programs', 'courses', 'partner-programmes',
                'for-individuals', 'executive-education', 'view-all-programs', 'all-programs') \
            or re.search(r'course-calend[ae]r|universities-and-institutes/[^/]+$', path):
        return ''
    return u


def inr(p):
    a, c = num(p['fee_amount']), p['fee_currency']
    return round(a * fx[c]) if a and c in fx else None


def weeks(p):
    w, d = num(p['duration_weeks']), num(p['duration_days'])
    return w if w else (round(d / 5, 1) if d else None)


MONTHS = {m: i for i, m in enumerate(['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'], 1)}
TODAY = datetime.date.today()


def first_date(raw, future=False):
    """First date in a catalogue's free-text start field, as ISO. Catalogues write
    "Apr 25-30, 2027", "03-Jan-2027", "2 Nov 2026" or ISO; anything else, or a
    date already past when future=True, comes back blank rather than guessed."""
    s = (raw or '').strip()
    m = re.match(r'(\d{4})-(\d{2})-(\d{2})', s)
    y = re.search(r'\b(20\d\d)\b', s)
    if m:
        d = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
    else:
        m1 = re.search(r'\b([A-Za-z]{3})[a-z]*\.?\s+(\d{1,2})\b', s)          # Apr 25
        m2 = re.search(r'\b(\d{1,2})[\s-]+([A-Za-z]{3})[a-z]*\b', s)          # 2 Nov / 03-Jan
        if m2 and m2.group(2).lower() in MONTHS and (not m1 or m2.start() < m1.start()):
            day, mon = int(m2.group(1)), MONTHS[m2.group(2).lower()]
        elif m1 and m1.group(1).lower() in MONTHS:
            day, mon = int(m1.group(2)), MONTHS[m1.group(1).lower()]
        else:
            return ''
        if not y:
            return ''
        d = (int(y.group(1)), mon, day)
    try:
        dt = datetime.date(*d)
    except ValueError:
        return ''
    return '' if future and dt < TODAY else dt.isoformat()


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
        'ns': first_date(g(p, 'next_start'), future=True), 'ls': first_date(g(p, 'last_known_start')),
        'cap': g(p, 'capstone'), 'imm': g(p, 'campus_immersion'), 'iv': g(p, 'industry_visit'),
        'ta': clip(g(p, 'target_audience'), 200), 'kt': clip(g(p, 'key_topics'), 300),
        # the name links to the first of these the page has: landing page, programme page, brochure
        'lu': specific(g(p, 'landing_url')), 'u': specific(p['url']), 'bu': specific(g(p, 'brochure_url')),
        'conf': p['match_confidence'], 'cat': clip(p['school_category'], 100),
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
        'call': c.get('call', ''), 'why': c.get('why', ''),
        # keyword phrases, so the page can match a typed programme idea to topics
        'kw': [k.strip().lower() for k in t['keywords'].split(';') if k.strip()]})

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

    # gaps the refresh closed: a fee that was blank last month and is published now
    changes['filled'] = sum(1 for k in cur.keys() & old.keys()
                            if not old[k]['fee_amount'] and cur[k]['fee_amount'])

# calls that moved since the last month's snapshot
csnaps = [p for p in sorted((R / 'snapshots').glob('calls-*.csv')) if p.stem[-7:] < this_month]
if csnaps and changes is not None:
    oldc = {r['topic_id']: r['call'] for r in csv.DictReader(open(csnaps[-1], encoding='utf-8'))}
    newc = {t['id']: t['call'] for t in topics if t['call']}
    changes['calls'] = [[tid, oldc.get(tid, ''), newc.get(tid, '')] for tid in sorted(set(oldc) | set(newc))
                        if oldc.get(tid, '') != newc.get(tid, '')]

# "What's new": the latest refresh plus the hand-written changelog, newest first
log = sorted(L('data/changelog.csv'), key=lambda r: r['date'], reverse=True) \
    if (R / 'data/changelog.csv').exists() else []
today = datetime.date.today()
whatsnew = {'ran': today.strftime('%d %b %Y'),
            'next': (today.replace(day=1) + datetime.timedelta(days=32)).replace(day=1).strftime('%d %b %Y'),
            'log': log[:12]}

# peer new-launch register (Product Team, hand-verified). The date a launch is
# placed on: its published launch date; failing that, a first cohort that has
# already run (the register's other confirmation rule); probables stay undated.
launches = None
if (R / 'data/peer_launches.csv').exists():
    meta = json.loads((R / 'data/peer_launches_meta.json').read_text(encoding='utf-8'))
    rows = []
    for r in L('data/peer_launches.csv'):
        ld, fc = r['launch_date'], r['first_cohort_date']
        if ld:
            eff, basis = (ld if len(ld) == 10 else ld + '-01'), 'launch'
        elif r['probable'] != 'Y' and len(fc) == 10 and fc <= meta['asof']:
            eff, basis = fc, 'first cohort'
        else:
            eff, basis = '', ''
        rows.append({'sc': r['school_slug'], 'n': r['programme'], 'ld': ld, 'ev': r['evidence'], 'fc': r['first_cohort'],
                     'fcd': fc, 'f': r['format'], 'dur': r['duration'], 'fee': r['fee'], 'pt': r['partner'],
                     'u': r['url'], 'prob': r['probable'] == 'Y', 'eff': eff, 'basis': basis})
    launches = dict(meta, rows=rows, excluded=[{'sc': r['school_slug'], 'n': r['programme'], 'why': r['why_not_counted'],
                                                'u': r['source']} for r in L('data/peer_launches_not_counted.csv')])

q = L('outputs/refresh_queue.csv') if (R / 'outputs/refresh_queue.csv').exists() else []
# programmes that appeared since last month's snapshot get a "new" mark in place
if changes:
    _added = {(s_, n_) for s_, n_, _t in changes['added']}
    for p in progs:
        if (p['sc'], p['n']) in _added:
            p['new'] = 1
d = {'asof': datetime.date.today().strftime('%d %b %Y'),
     'schools': [{'s': s['slug'], 'l': s['label'], 'g': s['group'], 'n': s['school']} for s in schools],
     'themes': list(dict.fromkeys(t['theme'] for t in tax)),
     'topics': topics, 'progs': progs, 'changes': changes, 'whatsnew': whatsnew, 'launches': launches,
     'fx': {k: v for k, v in fx.items() if k != 'INR'}, 'fxDate': L('data/fx.csv')[0]['set_on'],
     'quality': {'queue': len(q), 'noFee': sum(1 for p in progs if p['inr'] is None),
                 'noStart': sum(1 for p in progs if not p['ns']),
                 'fromSheet': sum(1 for p in progs if p['prov'] == 'team-sheet'),
                 'signals': len(L('data/demand_all.csv'))}}
(R / 'site' / 'data.json').write_text(json.dumps(d, separators=(',', ':'), ensure_ascii=False), encoding='utf-8')
print('site/data.json written:', len(json.dumps(d)), 'bytes;', len(progs), 'programmes')
