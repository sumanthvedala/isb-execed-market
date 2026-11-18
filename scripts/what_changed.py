#!/usr/bin/env python3
"""Before vs after, school by school, for the What changed tab.

Before is the team's competitor sheet as it was fed in (data/team_sheets/
competitor_sheet.csv, merged on 30 Sep 2026). After is the database today: the
programmes on the dashboard (programmes_tagged.csv, folded and classified) with
their catalogue fields. Run after classify.py and before build_data.py.

Every Before programme is traced to an After programme, or to the reason it is
not on the dashboard, using the same reading and name matching as the merge
(import_team_sheet.read_sheet and find_match). Then each matched pair is
compared field by field.

Writes
  outputs/what_changed.csv          one row per change
  outputs/what_changed_schools.csv  before and after counts per school tile

Counts reconcile per tile:
  after = before - removed - moved out - merged + moved in + added
"""
import csv, re, glob, collections, pathlib, sys

R = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / 'scripts'))
import import_team_sheet as its  # noqa: E402

BASELINE_DATE = '2026-09-30'      # when the sheet was merged in (data/changelog.csv)
SCHOOLS = its.SCHOOLS
PLATFORMS = its.PLATFORMS


def product_key(name):
    """classify.py's norm_name: the key that folds cohorts into one product.
    Keep in step with scripts/classify.py."""
    s = (name or '').lower()
    s = re.sub(r'\(.*?\)', '', s)
    s = re.sub(r'\[.*?\]', '', s)
    s = re.sub(r'batch[\s\-]*\d+|cohort\s*\d+|\b20\d\d\b|\b\d{1,2}(st|nd|rd|th)\b', '', s)
    s = re.sub(r'\bbatch\b', '', s)
    s = re.sub(r'[^a-z0-9 ]', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()


# why a catalogue row is not a dashboard programme (mirrors classify.py's EXCLUDE and MOOC)
_DEGREE = re.compile(r'\bmaster of\b|\bmasters? in\b|\be?mba\b|\bpgpx\b', re.I)
_ACADEMIC = re.compile(r'faculty development|case teaching|case writing|case pedagog|doctoral|'
                       r'participant.cent(?:ere|re)d learning|research and academic publishing|'
                       r'teaching effectiveness|for teachers|programme for faculty', re.I)
_MOOC = re.compile(r'coursera|\bedx\b|edx\.org|^iimbx', re.I)


def out_of_scope(row):
    blob = ' '.join(row.get(k, '') or '' for k in ('programme_name', 'school_category', 'target_audience'))
    if _DEGREE.search(blob):
        return 'degree programme, out of scope'
    if _ACADEMIC.search(blob):
        return 'faculty or academic programme, out of scope'
    if _MOOC.search(' '.join(row.get(k, '') or '' for k in ('partner', 'url', 'programme_name'))):
        return 'Coursera or edX course, out of scope'
    return 'out of scope'


# ---------------------------------------------------------------- values
SYM = {'INR': '₹', 'USD': '$', 'EUR': '€', 'GBP': '£', 'SGD': 'S$', 'CHF': 'CHF ', 'CNY': 'CN¥'}


def money(ccy, amt):
    if amt in (None, ''):
        return ''
    a = float(amt)
    if ccy == 'INR':                                  # Indian grouping: 3,50,000
        s = f'{int(round(a))}'
        head, tail = s[:-3], s[-3:]
        head = re.sub(r'(\d)(?=(\d\d)+$)', r'\1,', head)
        txt = (head + ',' if head else '') + tail
    else:
        txt = f'{a:,.0f}' if a == int(a) else f'{a:,.2f}'
    return SYM.get(ccy, (ccy + ' ') if ccy else '') + txt


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def weeks_from(weeks, days):
    w, d = num(weeks), num(days)
    return w if w else (round(d / 5, 1) if d else None)


def is_link(u):
    """the sheet's link column also holds PDF file names and programme titles"""
    u = (u or '').strip().lower()
    return u.startswith(('http://', 'https://', 'www.')) or bool(re.match(r'^[a-z0-9-]+(\.[a-z0-9-]+)+/', u))


def same_name(a, b):
    """cosmetic differences are not a rename: '&' or 'and', Program or Programme,
    punctuation, batch numbers, years and bracketed codes"""
    return its.core(its.norm_name(product_key(a))) == its.core(its.norm_name(product_key(b)))


def norm_url(u):
    u = (u or '').strip().lower()
    u = re.sub(r'^https?://', '', u)
    u = re.sub(r'^www\.', '', u)
    u = re.split(r'[?#]', u)[0]
    return u.rstrip('/')


_STOP = {'and', 'or', 'the', 'of', 'in', 'for', 'with', 'a', 'an', 'to', 'who', 'are', 'at', 'on', 'from', 'level'}


def words(s):
    return frozenset(w for w in re.findall(r'[a-z0-9]+', (s or '').lower()) if w not in _STOP)


def date_of(v):
    d = its.to_date(v)
    if d:
        return d
    m = re.search(r'(20\d\d)-(\d\d)-(\d\d)', v or '')
    if m:
        try:
            import datetime
            return datetime.date(*map(int, m.groups()))
        except ValueError:
            return None
    return None


def clip(s, n=140):
    s = (s or '').strip()
    return s[:n] + '…' if len(s) > n else s


# ---------------------------------------------------------------- load
incoming, dropped, _ = its.read_sheet()

catalogue = collections.defaultdict(list)
for f in sorted(glob.glob(str(R / 'data' / 'catalogues' / '*.csv'))):
    for r in csv.DictReader(open(f, encoding='utf-8')):
        if (r.get('programme_name') or '').strip():
            catalogue[r['school_slug']].append(r)

# the dashboard's programmes, and the catalogue row each one shows (build_data.py's g())
tagged = {}
for r in csv.DictReader(open(R / 'programmes_tagged.csv', encoding='utf-8')):
    tagged[(r['school_slug'], product_key(r['programme_name']))] = r
first_row = {}
for slug, rows in catalogue.items():
    for r in rows:
        first_row.setdefault((slug, r['programme_name'].strip()), r)

product_rows = collections.defaultdict(list)
for slug, rows in catalogue.items():
    for r in rows:
        product_rows[(slug, product_key(r['programme_name']))].append(r)

# programmes a school already sells through a platform (the merge's partner_names)
held_with_partner = {}
for slug, rows in catalogue.items():
    for r in rows:
        if (r.get('partner') or '').strip():
            held_with_partner.setdefault(its.norm_name(r['programme_name']), (slug, r))


def on_dashboard(slug, row):
    """the dashboard programme a catalogue row folds into, or (None, reason)"""
    t = tagged.get((slug, product_key(row['programme_name'])))
    if t is None:
        return None, out_of_scope(row)
    if t['theme'] == 'UNCLASSIFIED':
        return None, 'not tagged to any topic, so not on the dashboard'
    return t, ''


def tile_of(slug, partner):
    return ('partner' if (partner or '').strip() else 'own') if slug == 'isb' else ''


# ---------------------------------------------------------------- trace Before -> After
# a Before programme is one name the sheet filed under one school (cohorts are rows of it)
before = {}                         # (filed_under, norm name) -> dict
mapped = collections.defaultdict(list)   # after key (slug, product key) -> [sheet incoming rows]

for slug in SCHOOLS:
    have = catalogue.get(slug, [])
    idx = {its.norm_name(h['programme_name']): h for h in have}
    names = list(idx)
    for r in incoming.get(slug, []):
        filed = r['_sheet_school']
        bname = r['_sheet']['Programme Name'].strip()
        bk = (filed, its.norm_name(bname))
        b = before.setdefault(bk, dict(filed=filed, name=bname, rows=[], fate=None))
        b['rows'].append(r)
        n = its.norm_name(r['programme_name'])
        owner, hit, how = slug, None, ''
        if slug in PLATFORMS and n in held_with_partner:
            owner, hit = held_with_partner[n]
            how = 'held under the school'
        else:
            hit, how = its.find_match(n, idx, names)
        if hit is None:
            b['fate'] = b['fate'] or ('removed', slug, 'no longer in the database', r['partner'])
            continue
        t, why = on_dashboard(owner, hit)
        if t is None:
            b['fate'] = b['fate'] or ('removed', owner, why, hit.get('partner', ''))
            continue
        key = (owner, product_key(t['programme_name']))
        b['fate'] = ('kept', key, how)        # a kept cohort beats a dropped one
        mapped[key].append(r)

# rows the sheet read dropped: Coursera/edX and cohorts entered twice
dup_rows = collections.Counter()
for filed, slug, name, reason, row in dropped:
    if reason == 'same cohort entered twice':
        dup_rows[(slug, tile_of(slug, ''))] += 1
        continue
    bk = (filed, its.norm_name(row['Programme Name'].strip()))
    b = before.setdefault(bk, dict(filed=filed, name=row['Programme Name'].strip(), rows=[], fate=None))
    if b['fate'] is None:
        b['fate'] = ('removed', slug, 'Coursera or edX course, out of scope', '')

# ---------------------------------------------------------------- changes
changes = []


def add(slug, tile, change, prog='', before_name='', field='', kind='', bval='', aval='', note='', after_school=''):
    changes.append(dict(school_slug=slug, tile=tile, change=change, field=field, kind=kind,
                        programme=prog, before_name=before_name, before_value=bval,
                        after_value=aval, note=note, after_school=after_school or (slug if prog else '')))


tiles = collections.defaultdict(lambda: collections.Counter())   # (slug, tile) -> counts

# where each Before programme went
into = collections.defaultdict(list)       # after key -> [before keys]
for bk, b in before.items():
    fate = b['fate']
    if fate[0] == 'removed':
        _, slug, why, partner = fate
        tile = tile_of(slug, partner)
        tiles[(slug, tile)]['before'] += 1
        add(slug, tile, 'removed', before_name=b['name'], note=why)
        continue
    _, key, how = fate
    into[key].append(bk)

for key, bks in into.items():
    slug = key[0]
    t = tagged[key]
    tile = tile_of(slug, t['partner'])
    # the Before name closest to the After name stands for the programme; the others were duplicates
    own = sorted((bk for bk in bks if bk[0] == slug),
                 key=lambda bk: (before[bk]['name'].strip() != t['programme_name'].strip(),
                                 not same_name(before[bk]['name'], t['programme_name'])))
    moved = [bk for bk in bks if bk[0] != slug]
    for bk in moved:                                   # platform listing now under its school
        frm = bk[0]
        tiles[(frm, tile_of(frm, ''))]['before'] += 1
        tiles[(frm, tile_of(frm, ''))]['moved_out'] += 1
        add(frm, tile_of(frm, ''), 'moved_out', prog=t['programme_name'], before_name=before[bk]['name'],
            note=f"now under {SCHOOLS[slug]['school']}", after_school=slug)
    for bk in own:
        tiles[(slug, tile)]['before'] += 1
    if own:
        for bk in own[1:]:                             # two Before names, one After programme
            tiles[(slug, tile)]['merged'] += 1
            add(slug, tile, 'merged', prog=t['programme_name'], before_name=before[bk]['name'],
                note='same programme listed under another name')
    else:
        tiles[(slug, tile)]['moved_in'] += 1
        frm = sorted({SCHOOLS[bk[0]]['school'] for bk in moved})
        add(slug, tile, 'moved_in', prog=t['programme_name'], before_name=before[moved[0]]['name'],
            note='listed under ' + ' and '.join(frm) + ' before')

# programmes on the dashboard that no Before programme became
covered = set(into)
for key, t in tagged.items():
    if t['theme'] == 'UNCLASSIFIED' or key in covered:
        continue
    slug = key[0]
    tile = tile_of(slug, t['partner'])
    row = first_row.get((slug, t['programme_name'].strip()), {})
    prov = row.get('provenance', '')
    if not any(b['filed'] == slug for b in before.values()):
        origin = 'school not in Before'
    elif prov == 'isb-product-sheet':
        origin = "from ISB's product workbook"
    else:
        origin = "from the school's own website"
    tiles[(slug, tile)]['added'] += 1
    add(slug, tile, 'added', prog=t['programme_name'], note=origin)

# ---------------------------------------------------------------- field by field
FEATURES = [('capstone', 'Capstone'), ('campus_immersion', 'Campus immersion'),
            ('industry_visit', 'Industry visit'), ('alumni_status', 'Alumni status'),
            ('total_modules', 'Modules')]


def compare(slug, tile, prog, field, bvals, aval, show_b, show_a, same, alts=()):
    """bvals: Before values from every cohort row; aval: the After value the dashboard
    shows; alts: the same field on the programme's other cohort rows. A Before value
    found on any After cohort is not a change. show_b/show_a turn a value into text."""
    blank = (None, '', frozenset())
    bvals = [v for v in bvals if v not in blank]
    alts = [v for v in alts if v not in blank]
    if aval in blank and alts:
        aval = alts[0]
    has_a = aval not in blank
    if not bvals and not has_a:
        return
    if bvals and has_a and any(same(b, x) for b in bvals for x in [aval] + alts):
        return
    kind = 'filled' if not bvals else 'cleared' if not has_a else 'changed'
    tiles[(slug, tile)]['f_' + field] += 1
    add(slug, tile, 'field', prog=prog, field=field, kind=kind,
        bval=show_b(bvals[-1]) if bvals else '', aval=show_a(aval) if has_a else '')


for key, rows in mapped.items():
    slug = key[0]
    t = tagged[key]
    prog = t['programme_name']
    tile = tile_of(slug, t['partner'])
    a = first_row.get((slug, prog.strip()), {})
    rows = sorted(rows, key=lambda r: r['last_known_start'] or '')   # latest cohort last

    # name: a Before name that folds to a different product key was renamed or matched loosely
    bnames = [r['programme_name'] for r in rows]
    if not any(same_name(n, prog) for n in bnames):
        tiles[(slug, tile)]['f_name'] += 1
        add(slug, tile, 'field', prog=prog, field='name', kind='changed', bval=bnames[-1], aval=prog)

    cohorts = product_rows[key]
    fee_of = lambda r: (r['fee_currency'], num(r['fee_amount'])) if num(r.get('fee_amount')) is not None else None
    compare(slug, tile, prog, 'fee', [fee_of(r) for r in rows], fee_of(t),
            lambda v: money(*v), lambda v: money(*v),
            lambda b, x: b[0] == x[0] and abs(b[1] - x[1]) < 0.5, [fee_of(r) for r in cohorts])

    fmt = lambda v: (lambda f: f if f not in ('', 'Unknown') else None)((v or '').split(';')[0].strip())
    compare(slug, tile, prog, 'format', [fmt(r['format']) for r in rows], fmt(t['format']),
            str, str, lambda b, x: b == x, [fmt(r.get('format')) for r in cohorts])

    dur = lambda raw, w: (raw or '', w) if (raw or w) else None
    compare(slug, tile, prog, 'duration',
            [dur(r['duration_raw'], weeks_from(r['duration_weeks'], r['duration_days'])) for r in rows],
            dur(a.get('duration_raw', ''), weeks_from(t['duration_weeks'], t['duration_days'])),
            lambda v: v[0] or f'{v[1]:g} weeks', lambda v: v[0] or f'{v[1]:g} weeks',
            lambda b, x: (abs(b[1] - x[1]) <= max(0.15 * max(b[1], x[1]), 0.2)) if b[1] and x[1]
            else b[0].lower().strip() == x[0].lower().strip(),
            [dur(r.get('duration_raw', ''), weeks_from(r.get('duration_weeks'), r.get('duration_days'))) for r in cohorts])

    # dates and links: the value the dashboard shows, but any cohort's value counts as the same
    ns, ls = date_of(a.get('next_start', '')), date_of(a.get('last_known_start', ''))
    known = {d for r in cohorts for d in (date_of(r.get('next_start', '')), date_of(r.get('last_known_start', ''))) if d}
    compare(slug, tile, prog, 'start',
            [date_of(r['_sheet']['Start Date']) for r in rows],
            ns or ls or (max(known) if known else None),
            lambda d: d.isoformat(), lambda d: d.isoformat() + ('' if d == ns else ' (last run)'),
            lambda b, x: b == x or b in known)

    alinks = {norm_url(r.get(k, '')) for r in cohorts for k in ('landing_url', 'url', 'brochure_url')} - {''}
    best = next((a.get(k) for k in ('landing_url', 'url', 'brochure_url') if (a.get(k) or '').strip()), '')
    compare(slug, tile, prog, 'link',
            [r['url'].strip() if is_link(r['url']) else None for r in rows], best.strip() or None,
            str, str, lambda b, x: norm_url(b) in alinks)

    for f, _ in FEATURES:
        compare(slug, tile, prog, f, [r[f] for r in rows], (a.get(f) or '').strip() or None,
                str, str, lambda b, x: b == x, [(r.get(f) or '').strip() or None for r in cohorts])

    txt = lambda v: ((v or '').strip(), words(v)) if (v or '').strip() else None
    for f in ('eligibility', 'target_audience'):
        compare(slug, tile, prog, f, [txt(r[f]) for r in rows], txt(a.get(f)),
                lambda v: clip(v[0]), lambda v: clip(v[0]), lambda b, x: b[1] == x[1],
                [txt(r.get(f)) for r in cohorts])

    if (a.get('status') or '').strip():
        tiles[(slug, tile)]['discontinued'] += 1
        add(slug, tile, 'discontinued', prog=prog, note=clip(a.get('status_note', ''), 300))

# ---------------------------------------------------------------- write
after = collections.Counter((k[0], tile_of(k[0], t['partner'])) for k, t in tagged.items()
                            if t['theme'] != 'UNCLASSIFIED')
for k, n in dup_rows.items():
    tiles[k]['duplicate_rows'] += n

OUT = R / 'outputs'
cols = ['school_slug', 'tile', 'change', 'field', 'kind', 'programme', 'before_name',
        'before_value', 'after_value', 'note', 'after_school']
with open(OUT / 'what_changed.csv', 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=cols, quoting=csv.QUOTE_ALL)
    w.writeheader()
    w.writerows(sorted(changes, key=lambda c: (c['school_slug'], c['tile'], c['change'], c['field'],
                                               c['programme'] or c['before_name'])))

fields = ['name', 'fee', 'format', 'duration', 'start', 'link'] + [f for f, _ in FEATURES] + ['eligibility', 'target_audience']
scols = ['school_slug', 'tile', 'before', 'after', 'added', 'removed', 'moved_in', 'moved_out', 'merged',
         'discontinued', 'duplicate_rows'] + ['f_' + f for f in fields]
keys = sorted(set(tiles) | set(after))
bad = []
with open(OUT / 'what_changed_schools.csv', 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f, quoting=csv.QUOTE_ALL)
    w.writerow(scols)
    for k in keys:
        c = tiles[k]
        c['after'] = after.get(k, 0)
        c['removed'] = sum(1 for x in changes if (x['school_slug'], x['tile']) == k and x['change'] == 'removed')
        w.writerow([k[0], k[1]] + [c[x] for x in scols[2:]])
        expect = c['before'] - c['removed'] - c['moved_out'] - c['merged'] + c['moved_in'] + c['added']
        if expect != c['after']:
            bad.append(f'{k}: before {c["before"]} -> expected {expect}, after {c["after"]}')

kinds = collections.Counter(c['change'] if c['change'] != 'field' else 'field:' + c['field'] for c in changes)
print(f"what changed: {len(before)} programmes before, {sum(after.values())} after; "
      f"{len(changes)} changes -> outputs/what_changed.csv")
print('  ' + ', '.join(f'{k} {n}' for k, n in sorted(kinds.items())))
if bad:
    print('counts do not reconcile:\n  ' + '\n  '.join(bad))
    sys.exit(1)
