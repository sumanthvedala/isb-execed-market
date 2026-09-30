#!/usr/bin/env python3
"""Merges the team's competitor sheet (the Power BI source) into data/catalogues.

Run once per new version of the sheet:
    python scripts/import_team_sheet.py path/to/Competitor-Power_Bi_Sheet.xlsx

Rules
- Our catalogues stay the source of truth. A sheet row that matches a programme we
  already hold only fills fields that are blank on our side; it never overwrites.
- A sheet programme we do not hold is added, marked provenance=team-sheet, so the
  monthly refresh knows it has not been checked against a live page yet.
- Coursera and edX courses are out of scope and dropped.
- Rows with the same school, name and start date are the same cohort entered twice
  and are dropped. Same name with a different start date is a repeat cohort and is
  kept, because classify.py folds cohorts into one product with a run count.
- Faculty touchpoint, application fee and total sessions are not carried over.

The sheet is extracted to data/team_sheets/ so the merge can be re-run without it.
"""
import csv, re, sys, glob, difflib, datetime, pathlib, collections

ROOT = pathlib.Path(__file__).resolve().parent.parent
TODAY = datetime.date.today()
OUT = ROOT / 'data' / 'team_sheets'

SLUG = {'isb': 'isb', 'iim ahmedabad': 'iima', 'iim bangalore': 'iimb', 'iim calcutta': 'iimc',
        'iim indore': 'iimi', 'iim kozhikode': 'iimk', 'iim lucknow': 'iiml', 'sp jain': 'spjain',
        'hbs': 'hbs', 'hec paris': 'hec', 'insead': 'insead', 'kellogg': 'kellogg',
        'london': 'lbs', 'london business school': 'lbs', 'stanford': 'stanford', 'wharton': 'wharton',
        'emeritus': 'emeritus', 'imarticus': 'imarticus', 'jaro': 'jaro', 'times pro': 'timespro'}
PLATFORMS = {'emeritus', 'imarticus', 'jaro', 'timespro'}
# school prefix on a platform listing: "IIM Calcutta -", "ISB-", "Berkeley-"
# (the sheet also has "IM Calcutta-", "ISBCybersecurity", "... - IIM Kozhikode")
_OWN = (r'I?IM\s*(?:Ahmedabad|Bangalore|Calcutta|Indore|Kozhikode|Kozikode|Lucknow)|ISB(?=[A-Z\s-])|'
        r'SP\s*Jain|MIT\s*x\s*Pro|Berkeley|Emeritus|Kellogg|Wharton')
PREFIX = re.compile(rf'^({_OWN})\s*[-–:]?\s*', re.I)
SUFFIX = re.compile(rf'\s*[-–]?\s*({_OWN})\s*$', re.I)
SLUG.update({'iim kozikode': 'iimk', 'im calcutta': 'iimc', 'im indore': 'iimi', 'spjain': 'spjain',
             'iimahmedabad': 'iima', 'iimlucknow': 'iiml', 'iimkozhikode': 'iimk', 'iimindore': 'iimi',
             'iimcalcutta': 'iimc', 'iimbangalore': 'iimb'})
SCHOOLS = {r['slug']: r for r in csv.DictReader(open(ROOT / 'data' / 'schools.csv', encoding='utf-8'))}
HOME_CCY = {'hbs': 'USD', 'wharton': 'USD', 'stanford': 'USD', 'kellogg': 'USD', 'insead': 'EUR',
            'hec': 'EUR', 'lbs': 'GBP', 'imd': 'CHF'}

CAT_FIELDS = ['school', 'school_slug', 'region', 'programme_name', 'url', 'school_category', 'format',
              'duration_raw', 'duration_days', 'duration_weeks', 'fee_raw', 'fee_currency', 'fee_amount',
              'level', 'partner', 'target_audience', 'key_topics', 'is_new_2025_26', 'next_start',
              'source_note', 'channel', 'mark',
              # added with the team-sheet merge
              'last_known_start', 'end_date', 'capstone', 'campus_immersion', 'industry_visit',
              'total_modules', 'alumni_status', 'eligibility', 'provenance', 'last_verified']
FILLABLE = ['url', 'format', 'duration_raw', 'duration_days', 'duration_weeks', 'fee_raw', 'fee_currency',
            'fee_amount', 'level', 'target_audience', 'next_start', 'last_known_start', 'end_date',
            'capstone', 'campus_immersion', 'industry_visit', 'total_modules', 'alumni_status', 'eligibility']
BLANK = {'', 'tbd', 'not mentioned', 'not mentioend', 'na', 'n/a', 'nan', 'none', '-', 'no info', 'nil'}


def blank(v):
    return (v or '').strip().lower() in BLANK


def clean(v):
    v = re.sub(r'\s+', ' ', str(v if v is not None else '')).strip()
    return '' if blank(v) else v


def norm_name(s):
    s = (s or '').lower().replace('programme', 'program').replace('&', ' and ')
    s = re.sub(r'\(.*?\)|\[.*?\]', '', s)
    s = re.sub(r'[^a-z0-9 ]', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()


GENERIC = {'program', 'certificate', 'the', 'of', 'in', 'for', 'and', 'with', 'a', 'an', 'on', 'to',
           'online', 'course', 'professional'}


def core(n):
    return frozenset(t for t in n.split() if t not in GENERIC)


# words that mark a delivery variant of the same product, not a different product.
# "Accelerated", "Advanced", "Senior", "Fintech" etc. are deliberately absent:
# they name a different programme ("General Management" vs "Accelerated GM").
VARIANT = {'virtual', 'london', 'dubai', 'singapore', 'paris', 'mumbai', 'delhi', 'bangalore',
           'campus', 'live', 'blended', 'batch', 'strategies', 'management'}


def same_programme(a, b):
    """Two normalised names name the same product: identical once filler words
    go ("Leadership AI" / "Leadership with AI", "Essentials of Leadership" /
    "Leadership Essentials"), or differing only by a location, format or batch
    word ("Mergers and Acquisitions - Dubai")."""
    ca, cb = core(a), core(b)
    if not ca or not cb:
        return False
    if ca == cb:
        return True
    small, big = (ca, cb) if len(ca) <= len(cb) else (cb, ca)
    extra = {t for t in big - small if not t.isdigit()}
    return len(small) >= 2 and small <= big and extra <= VARIANT


def yes_no(v):
    v = clean(v).lower()
    return 'Yes' if v.startswith('yes') else 'No' if v.startswith('no') else ''


def to_date(v):
    if v is None or v == '':
        return None
    if isinstance(v, datetime.datetime):
        return v.date()
    if isinstance(v, datetime.date):
        return v
    s = clean(v)
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%d-%m-%Y', '%d/%m/%Y', '%b-%d-%Y', '%d %b %Y', '%B %d, %Y'):
        try:
            return datetime.datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def fmt_of(mode, touch):
    m = clean(mode).lower()
    if not m:
        return 'Unknown'
    if 'classr' in m or 'classrom' in m or 'campus' in m:
        return 'Campus'
    if 'hybrid' in m or 'blend' in m:
        return 'Blended'
    if 'live' in m:
        return 'Live Online'
    if 'online' in m:
        # the sheet's "Online" covers both recorded and live-supported courses;
        # its own faculty-touch column is the only thing that separates them
        return 'Self-paced Online' if clean(touch).lower().startswith('low') else 'Live Online'
    return 'Unknown'


def level_of(ta):
    t = clean(ta).lower()
    if not t:
        return 'Unknown'
    if 'board' in t or 'director' in t:
        return 'Board'
    if 'cxo' in t or 'c-suite' in t or 'ceo' in t:
        return 'C-suite/Senior'
    if 'mid' in t:
        return 'Mid-career'
    if 'senior' in t:
        return 'Senior'
    if re.search(r'junior|young|early|emerging|entry|graduate', t):
        return 'Early/Emerging'
    if 'manager' in t or 'professional' in t or 'executive' in t:
        return 'Mixed'
    return 'Unknown'


def fee_of(raw, slug):
    s = clean(raw)
    if not s or re.search(r'free', s, re.I):
        return s, '', ''
    ccy = ('GBP' if '£' in s else 'SGD' if 'S$' in s else 'EUR' if ('€' in s or 'EUR' in s.upper())
           else 'USD' if ('$' in s or 'USD' in s.upper()) else
           'INR' if re.search(r'₹|rs|inr', s, re.I) else HOME_CCY.get(slug, 'INR'))
    m = re.search(r'\d[\d,]*(?:\.\d+)?', s)
    if not m:
        return s, '', ''
    amt = float(m.group(0).replace(',', ''))
    return s, ccy, str(int(amt)) if amt == int(amt) else str(amt)


def weeks_of(raw):
    s = clean(raw).lower()
    m = re.search(r'(\d+(?:\.\d+)?)\s*(day|week|month|year|yr)', s)
    if not m:
        return '', ''
    n, u = float(m.group(1)), m.group(2)
    if u == 'day':
        return str(int(n)), str(round(n / 5, 1))
    mult = {'week': 1, 'month': 4.33, 'year': 52, 'yr': 52}[u]
    return '', str(round(n * mult, 1))


# ---------------------------------------------------------------- extract
def extract(xlsx):
    import openpyxl
    wb = openpyxl.load_workbook(xlsx, read_only=True, data_only=True)

    def sheet(prefix):
        ws = next(w for w in wb.worksheets if w.title.strip().lower().startswith(prefix))
        rows = list(ws.iter_rows(values_only=True))
        head = [str(h).strip() if h else '' for h in rows[0]]
        seen, cols = collections.Counter(), []
        for h in head:                      # the sheet repeats "Duration"
            seen[h] += 1
            cols.append(h if seen[h] == 1 else f'{h}.{seen[h]-1}')
        return [dict(zip(cols, r)) for r in rows[1:] if any(r)]

    v3 = sheet('master sheet 3')
    # sheet 3 dropped the platform competitors; v2 is the only place they exist
    v2 = [r for r in sheet('master sheet-2')
          if SLUG.get(clean(r.get('School Name')).lower()) in PLATFORMS]
    OUT.mkdir(parents=True, exist_ok=True)
    keep = ['School Name', 'Programme Name', 'Programme Fee', 'Duration', 'Learning Mode',
            'Faculty Touch Point', 'Start Date', 'End Date', 'Alumni Status', 'Total Modules',
            'Campus Immersion', 'Capstone Projects', 'Target Audience', 'Industry Visit',
            'Eligibility Criteria', 'Source Link', 'sheet_version']
    rows = [dict(r, sheet_version='v3') for r in v3] + [dict(r, sheet_version='v2') for r in v2]
    with open(OUT / 'competitor_sheet.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=keep, extrasaction='ignore', quoting=csv.QUOTE_ALL)
        w.writeheader()
        for r in rows:
            r = {k.strip(): v for k, v in r.items()}
            for k in ('Start Date', 'End Date'):
                d = to_date(r.get(k))
                r[k] = d.isoformat() if d else clean(r.get(k))
            w.writerow({k: clean(r.get(k)) for k in keep})
    print(f'extracted {len(rows)} rows -> data/team_sheets/competitor_sheet.csv')


# ---------------------------------------------------------------- merge
def merge():
    src = list(csv.DictReader(open(OUT / 'competitor_sheet.csv', encoding='utf-8')))
    stats = collections.Counter()
    incoming = collections.defaultdict(list)
    seen = set()
    for r in src:
        slug = SLUG.get(r['School Name'].strip().lower())
        name = r['Programme Name'].strip()
        if not slug or not name:
            stats['unknown school'] += 1
            continue
        partner = ''
        if slug in PLATFORMS:
            # "IIM Kozhikode-Chief Product Officer Programme" on Emeritus is IIM-K's
            # product delivered by Emeritus: it belongs to IIM-K, with the platform
            # as partner, or every school-branded platform course is counted twice.
            name = re.sub(r'^ISB[-–\s]+(?=ISB\b)', '', name)   # "ISB- ISB Venture ..."
            m = PREFIX.match(name) or SUFFIX.search(name)
            if m:
                who = re.sub(r'\s+', ' ', m.group(1)).strip().lower()
                owner = SLUG.get(who) or SLUG.get(who.replace(' ', ''))
                name = (name[m.end():] if m.start() == 0 else name[:m.start()]).strip()
                if owner and owner not in PLATFORMS:
                    partner = SCHOOLS[slug]['school']
                    slug = owner
                    name = re.sub(r'^ISB\s+', '', name)       # "ISB- ISB Venture Capital ..."
                    stats['platform row re-attributed to its school'] += 1
            name = re.sub(r'\s*[-–]?\s*batch\s*-?\s*\d*\s*$', '', name, flags=re.I).strip()
        link = r['Source Link'].lower()
        if 'coursera.org' in link or 'edx.org' in link or name.lower().startswith('iimbx'):
            stats['dropped: coursera/edx'] += 1
            continue
        k = (slug, norm_name(name), r['Start Date'])
        if k in seen:
            stats['dropped: same cohort entered twice'] += 1
            continue
        seen.add(k)
        start = to_date(r['Start Date'])
        raw, ccy, amt = fee_of(r['Programme Fee'], slug)
        days, weeks = weeks_of(r['Duration'])
        incoming[slug].append(dict(
            school=SCHOOLS[slug]['school'], school_slug=slug, region=SCHOOLS[slug]['region'],
            programme_name=name, url=r['Source Link'], school_category='',
            format=fmt_of(r['Learning Mode'], r['Faculty Touch Point']),
            duration_raw=clean(r['Duration']), duration_days=days, duration_weeks=weeks,
            fee_raw=raw, fee_currency=ccy, fee_amount=amt, level=level_of(r['Target Audience']),
            partner=partner, target_audience=clean(r['Target Audience']), key_topics='', is_new_2025_26='',
            next_start=start.isoformat() if start and start >= TODAY else '',
            last_known_start=start.isoformat() if start else '',
            end_date=clean(r['End Date']), capstone=yes_no(r['Capstone Projects']),
            campus_immersion=yes_no(r['Campus Immersion']), industry_visit=yes_no(r['Industry Visit']),
            total_modules=clean(r['Total Modules']) if re.fullmatch(r'\d+', clean(r['Total Modules'])) else '',
            alumni_status=yes_no(r['Alumni Status']), eligibility=clean(r['Eligibility Criteria'])[:200],
            source_note=f"team competitor sheet {r['sheet_version']}",
            channel='Partner' if partner else '', mark='(P)' if partner else '',
            provenance='team-sheet', last_verified=''))

    # names already sold by a school through a platform: a platform row with the
    # same name is the same product and must not be counted twice
    partner_names = set()
    for f in glob.glob(str(ROOT / 'data' / 'catalogues' / '*.csv')):
        for r in csv.DictReader(open(f, encoding='utf-8')):
            if (r.get('partner') or '').strip():
                partner_names.add(norm_name(r['programme_name']))

    report, matches = [], []
    for slug in SCHOOLS:
        path = ROOT / 'data' / 'catalogues' / f'{slug}.csv'
        have = list(csv.DictReader(open(path, encoding='utf-8'))) if path.exists() else []
        for h in have:
            for c in CAT_FIELDS:
                h.setdefault(c, '')
            if not h['provenance']:
                h['provenance'] = 'catalogue-capture'
            if not h['last_verified']:
                m = re.search(r'(20\d\d-\d\d-\d\d)', h.get('source_note', ''))
                h['last_verified'] = m.group(1) if m else '2026-09-24'
            # a start date in the past is history, not the next start
            d = to_date(h['next_start'])
            if d and d < TODAY:
                h['last_known_start'] = h['last_known_start'] or d.isoformat()
                h['next_start'] = ''
        idx = {norm_name(h['programme_name']): h for h in have}
        names = list(idx)
        added = filled = matched = 0
        for r in incoming.get(slug, []):
            n = norm_name(r['programme_name'])
            if slug in PLATFORMS and n in partner_names:
                stats['dropped: platform row already held under a school'] += 1
                continue
            hit = idx.get(n)
            if not hit:
                close = difflib.get_close_matches(n, names, 1, 0.9)
                hit = idx.get(close[0]) if close else None
            if not hit:
                alt = [x for x in names if same_programme(n, x)]
                hit = idx.get(alt[0]) if len(alt) == 1 else None
                if hit:
                    matches.append((slug, r['programme_name'], hit['programme_name']))
            if hit:
                matched += 1
                for c in FILLABLE:
                    if blank(hit.get(c)) and not blank(r.get(c)):
                        hit[c] = r[c]
                        filled += 1
                # a later cohort in the sheet is still a real, dated run
                if r['next_start'] and (not hit['next_start'] or r['next_start'] < hit['next_start']):
                    hit['next_start'] = r['next_start']
            else:
                have.append(r)
                idx[n] = r
                names.append(n)
                added += 1
        if have:
            with open(path, 'w', newline='', encoding='utf-8') as f:
                w = csv.DictWriter(f, fieldnames=CAT_FIELDS, extrasaction='ignore', quoting=csv.QUOTE_ALL)
                w.writeheader()
                w.writerows(have)
        report.append((slug, len(have) - added, matched, added, filled))

    print('\nschool     held  matched  added  fields-filled')
    for s, h, m, a, f in report:
        print(f'{s:9s} {h:5d} {m:8d} {a:6d} {f:9d}')
    for k, v in stats.items():
        print(f'{k}: {v}')
    # word-set matches are the ones a human should eyeball
    with open(OUT / 'name_matches_to_review.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f, quoting=csv.QUOTE_ALL)
        w.writerow(['school_slug', 'sheet_name', 'matched_to'])
        w.writerows(matches)
    print(f'{len(matches)} word-set matches written to data/team_sheets/name_matches_to_review.csv')


if __name__ == '__main__':
    if len(sys.argv) > 1:
        extract(sys.argv[1])
    merge()
