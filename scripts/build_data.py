#!/usr/bin/env python3
"""Builds site/data.json from the analysis outputs. Run after analyse.py and
demand_index.py. Keeping this separate from the page means a refresh rewrites
one JSON file and the HTML diff stays empty."""
import csv, json, glob, collections, pathlib, datetime, re, urllib.parse
from linkkind import kind, LABEL
R = pathlib.Path(__file__).resolve().parent.parent
L = lambda p: list(csv.DictReader(open(R / p, encoding='utf-8')))
num = lambda v: float(v) if re.fullmatch(r'\d+(\.\d+)?', (v or '').strip()) else None

schools = L('data/schools.csv')
S = [s['slug'] for s in schools]
fx = {r['currency']: float(r['inr_per_unit']) for r in L('data/fx.csv')}
prog = L('programmes_tagged.csv'); tax = L('data/taxonomy.csv')
tp = {r['topic_id']: r for r in L('outputs/matrix_topic_full.csv')}
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


def page(u):
    """a link that opens one programme's own page: not a news article, a
    course-listing site, a home page, catalogue index or calendar, a short
    link or a document (scripts/linkkind.py). A URL several programmes share
    is an index too."""
    u = (u or '').strip()
    return u if kind(u) == 'page' and _shared[u] < 3 else ''


def brochure(p):
    """the brochure column if it holds a usable link; failing that, a PDF that
    was captured into the programme-page column"""
    b = g(p, 'brochure_url')
    if kind(b) in ('brochure', 'page'):
        return b
    return p['url'].strip() if kind(p['url']) == 'brochure' else ''


# CXO programmes: named for a C-suite role, or filed under C-suite by the
# school, whatever the format. The school pages list these first.
_CXO_NAME = re.compile(r'\bchief\b|\bc[- ]?suite\b|\bcxos?\b|\b(ceo|cfo|cto|cmo|chro|coo|cio)s?\b', re.I)
_CXO_CAT = re.compile(r'c[- ]?suite|\bcxo', re.I)


def cxo(p):
    return 1 if _CXO_NAME.search(p['programme_name']) or _CXO_CAT.search(p['school_category'] or '') else 0


# Programme type: the grouping every school page, tile, filter and median uses.
# Each programme has exactly one type, so a C-suite programme never appears again
# under its format. Topic-focused programmes (TFP, ISB's own term) are short
# programmes on one topic: up to two weeks of contact on campus, or under 12
# weeks online. Longer online programmes, live or cohort-based, count as live online.
TYPES = ['C-suite', 'Blended', 'Live online', 'TFP campus', 'TFP online', 'Long campus', 'Self-paced', 'Not published']


def ptype(p, fmt, w):
    if cxo(p):
        return 'C-suite'
    if fmt == 'Blended':
        return 'Blended'
    if fmt == 'Online':                      # cohort-based online courses are short unless they say otherwise
        return 'Live online' if w is not None and w >= 12 else 'TFP online'
    if fmt == 'Live Online':
        return 'TFP online' if w is not None and w < 12 else 'Live online'
    if fmt == 'Campus':
        return 'Long campus' if w is not None and w > 2 else 'TFP campus'
    if fmt == 'Self-paced Online':
        return 'Self-paced'
    return 'Not published'


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


_MON = r'jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec'


def _dates(seg):
    """the dates in one stretch of text, in order, as [day or None, month, year or None]; a
    range is two dates. '15-18 Feb 2027' gives [15,2,None], [18,2,2027]: the missing parts
    are filled from the neighbours by runs()"""
    out, cur = [], {}
    for tok in re.findall(r'\d{4}|\d{1,2}|[a-z]+|-', seg):
        if tok == '-':
            if cur:
                out.append(cur); cur = {}
        elif len(tok) == 4 and tok.isdigit():
            if cur:
                cur['y'] = int(tok)
            elif out and 'y' not in out[-1]:
                out[-1]['y'] = int(tok)
        elif tok.isdigit():
            if 'd' in cur:
                out.append(cur); cur = {}
            cur['d'] = int(tok)
        elif tok[:3] in MONTHS and re.fullmatch(r'(?:%s)[a-z]*' % _MON, tok):
            if 'm' in cur:
                out.append(cur); cur = {}
            cur['m'] = MONTHS[tok[:3]]
    if cur:
        out.append(cur)
    return out


def runs(raw):
    """Every run a free-text date field names, as (start, end, precise) with ISO dates; a run
    given only as a month ("Jan 2027") has start 'YYYY-MM' and precise False. Catalogues write
    "Apr 25-30, 2027", "Nov 30-Dec 4, 2026", "05 October - 18 December 2026", "10-02-2027"
    (day first), "Jan 2027" or several runs split by ';' or '&'. Anything without a year is
    left out rather than guessed."""
    s = (raw or '').lower().replace('–', '-').replace('—', '-')
    s = re.sub(r'\(.*?\)|module\s*\d+\s*:|modular', ' ', s)
    s = re.sub(r'(\d)(st|nd|rd|th)\b', r'\1', s)
    s = re.sub(r'\b(\d{4})-(\d\d)-(\d\d)\b', lambda m: f'{int(m[3])} {list(MONTHS)[int(m[2]) - 1]} {m[1]}'
               if 1 <= int(m[2]) <= 12 else m[0], s)
    s = re.sub(r'\b(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})\b', lambda m: f'{int(m[1])} {list(MONTHS)[int(m[2]) - 1]} {m[3]}'
               if 1 <= int(m[2]) <= 12 else m[0], s)
    s = re.sub(r'\b(\d{1,2})-([a-z]{3,})-(\d{4})\b', r'\1 \2 \3', s)
    s = re.sub(r'\bto\b', '-', s)
    segs = [_dates(x) for x in re.split(r';|\s&\s|\sand\s', s)]
    for i in range(len(segs) - 2, -1, -1):          # "Jan 30 & Feb 6, 2027": the year comes last
        if segs[i] and not any('y' in d for d in segs[i]):
            y = next((d['y'] for later in segs[i + 1:] for d in later if 'y' in d), None)
            if y:
                segs[i][-1]['y'] = y
    out = []
    for ds in segs:
        for i, d in enumerate(ds):                    # month and year from the nearest neighbour
            for k in ('m', 'y'):
                if k not in d:
                    src = next((x[k] for x in ds[i + 1:] if k in x), None) or \
                          next((x[k] for x in reversed(ds[:i]) if k in x), None)
                    if src:
                        d[k] = src
        ds = [d for d in ds if 'm' in d and 'y' in d]
        if not ds:
            continue
        iso = lambda d: (f"{d['y']:04d}-{d['m']:02d}-{d['d']:02d}" if 'd' in d else f"{d['y']:04d}-{d['m']:02d}")
        try:
            for d in ds:
                if 'd' in d:
                    datetime.date(d['y'], d['m'], d['d'])
        except ValueError:
            continue
        a, b = ds[0], ds[-1]
        if len(ds) > 1 and iso(a) > iso(b) and a.get('y') == b.get('y'):
            a['y'] -= 1                               # "Dec 28 - Jan 3, 2027"
        out.append((iso(a), iso(b) if len(ds) > 1 else '', 'd' in a))
    return sorted(set(out))


def _iso_end(r):
    """a run's end date for comparison; a month-only date counts to the month's end"""
    e = r[1] or r[0]
    return e if len(e) == 10 else e + '-31'


# what a start field says when it gives no date
NO_DATE = [(r'rolling|any ?time|enrol immediately|flexible|self.paced|on.demand', 'Enrol any time'),
           (r'to be announced|\btba\b|\btbh\b|\btbd\b|to be confirmed', 'Dates to be announced'),
           (r'multiple|several|every month|monthly|quarterly', 'Several runs a year')]

# the class pattern, where a page states it: weekends, evenings, hours a week, live sessions
SCHED = re.compile(r'\d+(?:\s*(?:-|to)\s*\d+)?\s*(?:hours?|hrs?)\s*(?:per|a|/)\s*week'
                   r'|\d+\s*x\s*\d+\s*h(?:ours?|rs?)?\s*(?:per|a|/)\s*week'
                   r'|(?:live (?:online |virtual )?)?weekends?(?: sessions?| classes)?|weekday evenings?|evenings?'
                   r'|(?:\d+|two|three|four|five|six)(?: \d+-hour)? live (?:virtual |online )?sessions?', re.I)


def timing(p):
    """next run, other upcoming runs, last run, a run under way, a no-date note and the class
    pattern, from the catalogue's start and end fields"""
    rs = runs(g(p, 'next_start'))
    up = [r for r in rs if r[0] >= TODAY.isoformat()[:len(r[0])] and not (len(r[0]) == 7 and r[0] == TODAY.isoformat()[:7]
                                                                          and not r[1])]
    now = [r for r in rs if r not in up and _iso_end(r) >= TODAY.isoformat()]
    past = [r for r in rs if r not in up and r not in now]
    ls, le = first_date(g(p, 'last_known_start')), first_date(g(p, 'end_date'))
    if le and (not ls or le < ls):
        le = ''
    if past and (not ls or past[-1][0] > ls):
        ls, le = past[-1][0], past[-1][1]
    note = ''
    if not rs:
        txt = g(p, 'next_start').lower()
        note = next((lab for pat, lab in NO_DATE if re.search(pat, txt)), '')
    if not up and not now and p['format'].startswith('Self-paced'):
        note = 'Enrol any time'
    sch = g(p, 'schedule') or ' · '.join(dict.fromkeys(m.group(0).strip().lower() for f in ('duration_raw', 'target_audience')
                                                       for m in SCHED.finditer(g(p, f))))
    return {'ns': up[0][0] if up else '', 'ne': up[0][1] if up else '',
            'nx': [[a, b] for a, b, _ in up[1:4]],
            'cur': [now[0][0], now[0][1]] if now and not up else None,
            'ls': ls, 'le': le, 'nd': note, 'sch': clip(sch, 80)}


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
        **timing(p),
        'cap': g(p, 'capstone'), 'imm': g(p, 'campus_immersion'), 'iv': g(p, 'industry_visit'),
        'ta': clip(g(p, 'target_audience'), 200), 'kt': clip(g(p, 'key_topics'), 300),
        # the name links to the first of these the page has: landing page, programme page, brochure
        'lu': page(g(p, 'landing_url')), 'u': page(p['url']), 'bu': brochure(p), 'cx': cxo(p),
        'ty': ptype(p, p['format'].split(';')[0].strip(), weeks(p)),
        'conf': p['match_confidence'], 'cat': clip(p['school_category'], 100),
        # why the programme looks discontinued; blank while it is on sale
        'gone': g(p, 'status_note') if g(p, 'status') else '',
        'prov': g(p, 'provenance'), 'lvf': g(p, 'last_verified')[:10], 'runs': int(p['scheduled_runs'] or 1)})

topics = []
for t in tax:
    m, d = tp.get(t['topic_id'], {}), di.get(t['topic_id'], {})
    topics.append({
        'id': t['topic_id'], 'n': t['topic'], 'th': t['theme'], 'st': t['subtheme'], 'ai': t['ai_era_flag'],
        'dem': int(m.get('demand_score') or 0), 'srcs': int(m.get('demand_sources') or 0),
        'geo': m.get('demand_geographies', ''), 'dsl': clip(m.get('demand_source_list', ''), 400),
        'idx': int(d.get('demand_index') or 0), 'out': int(d['outlook_2027_31']) if d.get('outlook_2027_31') else None,
        'why2': d.get('outlook_rationale', ''), 'sig': d.get('best_signal', ''),
        'isb': int(m.get('isb') or 0), 'peers': int(m.get('peers_present') or 0),
        'resid': m.get('supply_is_residual_bucket') == 'Y',
        # keyword phrases, so the page can match a typed programme idea to topics
        'kw': [k.strip().lower() for k in t['keywords'].split(';') if k.strip()]})

# programme-level change since the latest snapshot taken before this week began.
# Snapshots are weekly (programmes-YYYY-Www.csv, dated by their Monday) and, from
# before the weekly refresh, monthly (programmes-YYYY-MM.csv, dated by the month's end).
_monday = datetime.date.today() - datetime.timedelta(days=datetime.date.today().weekday())


def _snap_date(path):
    k = path.stem[len('programmes-'):]
    m = re.fullmatch(r'(\d{4})-W(\d{2})', k)
    if m:
        return datetime.date.fromisocalendar(int(m.group(1)), int(m.group(2)), 1), k
    m = re.fullmatch(r'(\d{4})-(\d{2})', k)
    if m:
        y, mo = int(m.group(1)), int(m.group(2))
        return (datetime.date(y + mo // 12, mo % 12 + 1, 1) - datetime.timedelta(days=1)), k
    return None, k


snaps = sorted((d, k, p) for p in (R / 'snapshots').glob('programmes-*.csv') for d, k in [_snap_date(p)] if d and d < _monday)
# programmes taken out of scope (data/renames.csv, decision `removed`) are not shown as dropped
_out_of_scope = {(r['school_slug'], r['old_name']) for r in csv.DictReader(open(R / 'data' / 'renames.csv', encoding='utf-8'))
                 if r['decision'].strip().lower() == 'removed'} if (R / 'data' / 'renames.csv').exists() else set()
changes = None
if snaps:
    sdate, skey, spath = snaps[-1]
    old = {(r['school_slug'], r['programme_name']): r for r in csv.DictReader(open(spath, encoding='utf-8'))}
    cur = {(p['school_slug'], p['programme_name']): p for p in prog}
    # a weekly snapshot is labelled by its Monday, a monthly one by its month
    changes = {'since': sdate.isoformat() if 'W' in skey else skey, 'weekly': 'W' in skey,
               'added': [[s, n, cur[(s, n)]['topic_id']] for (s, n) in cur.keys() - old.keys()],
               'dropped': [[s, n, old[(s, n)]['topic_id']] for (s, n) in old.keys() - cur.keys() if (s, n) not in _out_of_scope],
               'repriced': [[s, n, old[(s, n)]['fee_amount'], cur[(s, n)]['fee_amount']]
                            for (s, n) in cur.keys() & old.keys()
                            if old[(s, n)]['fee_amount'] and cur[(s, n)]['fee_amount']
                            and old[(s, n)]['fee_amount'] != cur[(s, n)]['fee_amount']]}

    # gaps the refresh closed: a fee that was blank last month and is published now
    changes['filled'] = sum(1 for k in cur.keys() & old.keys()
                            if not old[k]['fee_amount'] and cur[k]['fee_amount'])

# "What's new": the latest refresh plus the hand-written changelog, newest first
log = sorted(L('data/changelog.csv'), key=lambda r: r['date'], reverse=True) \
    if (R / 'data/changelog.csv').exists() else []
today = datetime.date.today()
# the refresh runs every Monday (.github/workflows/refresh.yml)
whatsnew = {'ran': today.strftime('%d %b %Y'), 'iso': today.isoformat(),
            'next': (today + datetime.timedelta(days=(7 - today.weekday()) or 7)).strftime('%d %b %Y'),
            'log': log[:12]}

# peer new-launch register (Product Team, hand-verified). The date a launch is
# placed on: its published launch date; failing that, a first cohort that has
# already run (the register's other confirmation rule); probables stay undated.
launches = None
if (R / 'data/peer_launches.csv').exists():
    meta = json.loads((R / 'data/peer_launches_meta.json').read_text(encoding='utf-8'))
    rows = []
    tag = {(r['school_slug'], r['programme']): r for r in L('outputs/launches_tagged.csv')} \
        if (R / 'outputs/launches_tagged.csv').exists() else {}
    for r in L('data/peer_launches.csv'):
        tg = tag.get((r['school_slug'], r['programme']), {})
        # url is the programme's own page and nothing else; the article or
        # brochure that evidences the launch is the source
        src = (r.get('source_url') or '').strip() or (r['url'] if kind(r['url']) != 'page' else '')
        ld, fc = r['launch_date'], r['first_cohort_date']
        if ld:
            eff, basis = (ld if len(ld) == 10 else ld + '-01'), 'launch'
        elif r['probable'] != 'Y' and len(fc) == 10 and fc <= meta['asof']:
            eff, basis = fc, 'first cohort'
        else:
            eff, basis = '', ''
        if eff and eff < meta['from']:
            continue                          # older than the rolling 12-month window
        rows.append({'sc': r['school_slug'], 'n': r['programme'], 'ld': ld, 'ev': r['evidence'], 'fc': r['first_cohort'],
                     'fcd': fc, 'f': r['format'], 'dur': r['duration'], 'fee': r['fee'], 'pt': r['partner'],
                     'u': r['url'] if kind(r['url']) == 'page' else '', 'src': src, 'srck': LABEL[kind(src)],
                     'th': tg.get('theme', ''), 'tid': tg.get('topic_id', ''), 'lv': tg.get('level', 'Unknown'),
                     'lvb': tg.get('level_basis', ''), 'prob': r['probable'] == 'Y', 'eff': eff, 'basis': basis})
    launches = dict(meta, rows=rows, excluded=[{'sc': r['school_slug'], 'n': r['programme'], 'why': r['why_not_counted'],
                                                'u': r['source']} for r in L('data/peer_launches_not_counted.csv')])

q = L('outputs/refresh_queue.csv') if (R / 'outputs/refresh_queue.csv').exists() else []
lq = L('outputs/link_queue.csv') if (R / 'outputs/link_queue.csv').exists() else []
# programmes the second pass looked for a page for, in the last 90 days, and found the school publishes none
_cut = (datetime.date.today() - datetime.timedelta(days=90)).isoformat()
nopage = sum(1 for r in (L('data/link_checks.csv') if (R / 'data/link_checks.csv').exists() else [])
             if r['checked_on'][:10] >= _cut)
# programmes that appeared since last month's snapshot get a "new" mark in place
if changes:
    _added = {(s_, n_) for s_, n_, _t in changes['added']}
    for p in progs:
        if (p['sc'], p['n']) in _added:
            p['new'] = 1
# What changed: the change history (scripts/what_changed.py, data/history/), one
# row per change, for the page to net out over the window the reader picks.
# A row points at its dashboard programme by index; a programme not on the
# dashboard is named instead. Link changes are always ours and stay out.
wc = None
if (R / 'outputs/what_changed.csv').exists():
    _at = {(p['sc'], p['n']): i for i, p in enumerate(progs)}
    # rechecks: lines in the weekly re-check log; the page says when none has run yet
    wc = {'start': '2026-09-30', 'today': datetime.date.today().isoformat(), 'rows': [],
          'rechecks': len(L('data/recheck_log.csv')) if (R / 'data/recheck_log.csv').exists() else 0}
    for c in L('outputs/what_changed.csv'):
        if c['field'] == 'link':
            continue
        i = _at.get((c['school_slug'], c['programme']), -1)
        note = re.sub(r'(; )?commit [0-9a-f]+$', '', c['note'])
        # 12, 13: the window in which the school made the change (scripts/what_changed.py)
        wc['rows'].append([c['date'], c['school_slug'], c['tile'], i, c['name'] if i < 0 else '', c['key'],
                           c['field'], c['kind'], c['before'], c['after'], 1 if c['basis'] == 'school' else 0, note,
                           c.get('seen_before', ''), c.get('seen_after', '') or c['date']])
d = {'asof': datetime.date.today().strftime('%d %b %Y'),
     'schools': [{'s': s['slug'], 'l': s['label'], 'g': s['group'], 'n': s['school'], 'r': s['region']} for s in schools],
     'types': TYPES,
     'themes': list(dict.fromkeys(t['theme'] for t in tax)),
     'topics': topics, 'progs': progs, 'changes': changes, 'whatsnew': whatsnew, 'launches': launches, 'wc': wc,
     'fx': {k: v for k, v in fx.items() if k != 'INR'}, 'fxDate': L('data/fx.csv')[0]['set_on'],
     'quality': {'queue': len(q), 'links': len(lq), 'noPage': nopage, 'noFee': sum(1 for p in progs if p['inr'] is None),
                 'noStart': sum(1 for p in progs if not p['ns']),
                 'fromSheet': sum(1 for p in progs if p['prov'] == 'team-sheet'),
                 'gone': sum(1 for p in progs if p['gone']),
                 'signals': len(L('data/demand_all.csv'))}}
(R / 'site' / 'data.json').write_text(json.dumps(d, separators=(',', ':'), ensure_ascii=False), encoding='utf-8')
print('site/data.json written:', len(json.dumps(d)), 'bytes;', len(progs), 'programmes')
