#!/usr/bin/env python3
"""The change history behind the What changed tab.

Every run compares the catalogues (data/catalogues/*.csv) with the state the
last run recorded (data/history/state.csv) and appends what moved to
data/history/changes.csv, dated today: programmes listed or no longer listed,
and changes to fee, duration, modules, format, topics taught, next start,
level, partner, link, programme features, eligibility, audience and the
likely-discontinued mark. The page picks a window (last week to last year)
and shows, per school, the net change between the start of that window and
now.

Each change records whether the school changed something or we changed our
record (basis 'school' or 'ours'):
  - a field filled or cleared is ours: we captured or removed a value;
  - a value replaced by another is the school's when the weekly re-check logged
    that programme as changed in data/recheck_log.csv in the week before, or,
    for fee, duration and modules, when both values were read from the school's
    own page on different dates (the old one by a check we recorded, not from the
    competitor sheet) and the move is under 50%; a bigger jump is almost always a
    capture error of ours (a missing digit, a parsing fix). Anything else is ours:
    a first check against the live page, or a correction such as a format rule;
  - a link is always ours;
  - the likely-discontinued mark, and a programme no longer listed, are the school's;
  - a programme newly listed is the school's when it came from the school's own
    listing (provenance catalogue-capture), ours when it came from a workbook or sheet;
  - a rename confirmed in data/renames.csv (scripts/apply_renames.py) is one change,
    'renamed', on the programme's new name, not the old one gone and a new one listed.
    The old name's earlier changes (a likely-discontinued mark, say) stay in the log
    but are left out of outputs/what_changed.csv, since they were the rename.

A programme no longer listed keeps its last recorded details in
data/history/removed.csv, so scripts/rename_candidates.py can still compare it.

When the school made a change, not when we recorded it. Each change carries
seen_before (the last day we read the old state on the school's own page or
listing) and seen_after (the first day we read the new state there). The school
made the change between the two. seen_before is blank when the old state never
came from the school's page (the competitor sheet, a workbook), and for a
programme marked likely discontinued it goes back to the programme's last run when
that is earlier: a programme that last ran in July 2025 could have been dropped at
any time since. The page places a change in a period only when this window is
short enough to date it; the rest it lists as found, date unknown.

History starts on 30 Sep 2026, when the team's competitor sheet was merged in;
scripts/backfill_history.py rebuilt the changes from then to 18 Nov 2026 from
the repository's history. Run after classify.py and before build_data.py.
Writes outputs/what_changed.csv: the log with the dashboard programme each
change belongs to.
"""
import csv, glob, re, datetime, pathlib, sys

R = pathlib.Path(__file__).resolve().parent.parent
HIST = R / 'data' / 'history'
HISTORY_START = '2026-09-30'

FIELDS = ['fee', 'duration', 'modules', 'format', 'topics', 'next_start', 'level', 'partner', 'link',
          'capstone', 'campus_immersion', 'industry_visit', 'alumni_status', 'eligibility',
          'target_audience', 'status']
STATE_COLS = ['school_slug', 'key', 'name', 'provenance', 'is_new', 'checked', 'first_seen', 'last_run'] + FIELDS
LOG_COLS = ['date', 'school_slug', 'key', 'name', 'field', 'kind', 'before', 'after', 'basis', 'note',
            'seen_before', 'seen_after']
MONTHS = {m: i for i, m in enumerate(['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'], 1)}


def last_run(r):
    """the programme's last run: last_known_start, else "last ran Jul 2025" in the status note"""
    d = clean(r.get('last_known_start'))
    if re.fullmatch(r'\d{4}-\d\d-\d\d', d):
        return d
    m = re.search(r'last ran ([A-Za-z]{3})[a-z]* (\d{4})', r.get('status_note') or '')
    return f'{m.group(2)}-{MONTHS[m.group(1).lower()]:02d}-01' if m and m.group(1).lower() in MONTHS else ''


def product_key(name):
    """classify.py's norm_name: cohorts and batch numbers fold into one programme.
    Keep in step with scripts/classify.py."""
    s = (name or '').lower()
    s = re.sub(r'\(.*?\)', '', s)
    s = re.sub(r'\[.*?\]', '', s)
    s = re.sub(r'batch[\s\-]*\d+|cohort\s*\d+|\b20\d\d\b|\b\d{1,2}(st|nd|rd|th)\b', '', s)
    s = re.sub(r'\bbatch\b', '', s)
    s = re.sub(r'[^a-z0-9 ]', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()


def clean(v):
    return re.sub(r'\s+', ' ', str(v or '')).strip()


def num(v):
    try:
        f = float(v)
        return str(int(f)) if f == int(f) else str(f)
    except (TypeError, ValueError):
        return ''


def weeks(r):
    w, d = num(r.get('duration_weeks')), num(r.get('duration_days'))
    return w or (num(round(float(d) / 5, 1)) if d else '')


def values(r):
    """the tracked fields of one catalogue row, as text"""
    amt = num(r.get('fee_amount'))
    raw_dur, wk = clean(r.get('duration_raw')), weeks(r)
    return {
        'fee': f"{clean(r.get('fee_currency')) or '?'} {amt}" if amt else '',
        'duration': f'{raw_dur}|{wk}' if (raw_dur or wk) else '',
        'modules': num(r.get('total_modules')),
        'format': clean(r.get('format')).split(';')[0].strip() if clean(r.get('format')) not in ('', 'Unknown') else '',
        'topics': '; '.join(sorted({t.strip() for t in clean(r.get('key_topics')).split(';') if t.strip()}, key=str.lower)),
        'next_start': clean(r.get('next_start')),
        'level': clean(r.get('level')) if clean(r.get('level')) != 'Unknown' else '',
        'partner': clean(r.get('partner')),
        'link': next((clean(r.get(k)) for k in ('landing_url', 'url', 'brochure_url') if clean(r.get(k))), ''),
        'capstone': clean(r.get('capstone')),
        'campus_immersion': clean(r.get('campus_immersion')),
        'industry_visit': clean(r.get('industry_visit')),
        'alumni_status': clean(r.get('alumni_status')),
        'eligibility': clean(r.get('eligibility')),
        'target_audience': clean(r.get('target_audience')),
        'status': clean(r.get('status')),
    }


def state_of(rows):
    """one entry per programme (school + folded name); the first row with a
    value for a field gives it, so a repeat cohort adds nothing"""
    st = {}
    for r in rows:
        name = clean(r.get('programme_name'))
        if not name:
            continue
        k = (r['school_slug'], product_key(name))
        v = values(r)
        if k not in st:
            # the day our record was last read from the school's own page; values that came
            # from the competitor sheet or a search snippet were never read there
            prov, note = clean(r.get('provenance')), clean(r.get('source_note')).lower()
            checked = clean(r.get('last_verified'))[:10] if prov not in ('team-sheet',) and 'snippet' not in note else ''
            st[k] = dict(school_slug=k[0], key=k[1], name=name, provenance=prov,
                         is_new=clean(r.get('is_new_2025_26')).upper()[:1], checked=checked, first_seen=checked,
                         last_run=last_run(r), **v)
        else:
            for f in FIELDS:
                if not st[k][f] and v[f]:
                    st[k][f] = v[f]
    return st


def carry_first_seen(old, cur):
    """the first day each programme was read on the school's page, kept from run to run"""
    for k, s in cur.items():
        o = (old or {}).get(k, {})
        firsts = [x for x in (o.get('first_seen', ''), o.get('checked', ''), s.get('checked', '')) if x]
        s['first_seen'] = min(firsts) if firsts else ''
    return cur


def catalogue_rows():
    return [r for f in sorted(glob.glob(str(R / 'data' / 'catalogues' / '*.csv')))
            for r in csv.DictReader(open(f, encoding='utf-8'))]


def recheck_changes():
    """(school, folded name) -> dates the weekly re-check found the programme changed"""
    out = {}
    p = R / 'data' / 'recheck_log.csv'
    if p.exists():
        for r in csv.DictReader(open(p, encoding='utf-8')):
            if clean(r.get('outcome')).lower() == 'changed':
                out.setdefault((r['school_slug'], product_key(r['programme_name'])), []).append(
                    (clean(r.get('checked_on'))[:10], {f.strip() for f in clean(r.get('fields')).split(';') if f.strip()}))
    return out


def discontinued():
    """programmes a school confirmed discontinued: (school, key) -> evidence"""
    p = R / 'data' / 'renames.csv'
    return {(r['school_slug'], product_key(r['old_name'])): clean(r.get('evidence'))
            for r in csv.DictReader(open(p, encoding='utf-8'))
            if clean(r.get('decision')).lower() == 'discontinued'} if p.exists() else {}


def renames():
    """confirmed renames: (school, old key) -> (school, new key, old name, new name, evidence)"""
    p = R / 'data' / 'renames.csv'
    out = {}
    if p.exists():
        for r in csv.DictReader(open(p, encoding='utf-8')):
            if clean(r.get('decision')).lower() == 'renamed':
                out[(r['school_slug'], product_key(r['old_name']))] = (
                    r['school_slug'], product_key(r['new_name']), clean(r['old_name']), clean(r['new_name']), clean(r.get('evidence')))
    return out


def diff(old, new, date, rechecked=None, renamed=None, prev_run=''):
    """the changes between two states, recorded on `date`. prev_run is the date of the
    run that recorded `old`: a programme newly on a school's listing was not there then."""
    rechecked = rechecked or {}
    renamed = renamed or {}
    d0 = (datetime.date.fromisoformat(date) - datetime.timedelta(days=8)).isoformat()
    ev = []

    def seen(a, b):
        """(last day the old state was read on the school's page, first day the new one was)"""
        sb = (a or {}).get('checked', '')
        sa = (b or {}).get('checked', '')
        return sb, sa if sa and sa > sb and sa <= date else date

    def add(k, s, field, kind, before, after, basis, note='', sb='', sa=''):
        ev.append(dict(date=date, school_slug=k[0], key=k[1], name=s['name'], field=field, kind=kind,
                       before=before, after=after, basis=basis, note=note, seen_before=sb, seen_after=sa or date))

    # a confirmed rename: the old name gone and the new one present is one change
    gone, fresh = old.keys() - new.keys(), new.keys() - old.keys()
    for k in sorted(gone):
        rn = renamed.get(k)
        if rn and (rn[0], rn[1]) in new:
            nk = (rn[0], rn[1])
            # the new name was on the school's page by the day we first read it there; if that
            # is before we last saw the old name, the rename came earlier and cannot be dated
            sa = min(x for x in ((old.get(nk) or new[nk]).get('first_seen', ''), date) if x)
            sb = old[k].get('checked', '')
            ev.append(dict(date=date, school_slug=nk[0], key=nk[1], name=new[nk]['name'], field='listed', kind='renamed',
                           before=old[k]['name'], after=new[nk]['name'], basis='school', note=rn[4],
                           seen_before=sb if sb and sb < sa else '', seen_after=sa))
            gone = gone - {k}
            fresh = fresh - {nk}
    for k in sorted(fresh):
        s = new[k]
        launch = s['is_new'] == 'Y'
        on_listing = s['provenance'] in ('catalogue-capture', '')
        # newly on a school's listing: not there at the previous weekly run, if that was recent
        sb = prev_run if on_listing and prev_run and \
            (datetime.date.fromisoformat(date) - datetime.date.fromisoformat(prev_run)).days <= 14 else ''
        add(k, s, 'listed', 'added', '', s['name'], 'school' if on_listing else 'ours',
            'new launch' if launch else ('from the school\'s listing' if on_listing
                                         else f"from {s['provenance'].replace('-', ' ')}"),
            sb, seen(None, s)[1])
    confirmed = discontinued()
    for k in sorted(gone):
        add(k, old[k], 'listed', 'removed', old[k]['name'], '', 'school', confirmed.get(k) or 'no longer in the catalogue',
            old[k].get('checked', ''), date)
    for k in sorted(old.keys() & new.keys()):
        a, b = old[k], new[k]
        checks = [fs for dt, fs in rechecked.get(k, []) if d0 <= dt <= date]
        for f in FIELDS:
            x, y = a.get(f, ''), b.get(f, '')
            if x == y:
                continue
            sb, sa = seen(a, b)
            if f == 'status':
                kind = 'discontinued' if y else 'relisted'
                # dropped some time after its last run, if that is before we last saw it listed
                lr = b.get('last_run', '') or a.get('last_run', '')
                if y and lr and (not sb or lr < sb):
                    sb = lr
                add(k, b, f, kind, x, y, 'school', '', sb, sa)
                continue
            elif not x:
                kind, basis = 'filled', 'ours'
            elif not y:
                kind, basis = 'cleared', 'ours'
            else:
                kind = 'changed'
                basis = 'school' if f != 'link' and any(not fs or f in fs for fs in checks) else 'ours'
                note = ''
                if basis == 'ours' and f in ('fee', 'duration', 'modules') and a.get('checked') and a['checked'] < date \
                        and moved_under(f, x, y, 0.5):
                    basis, note = 'school', f"read from the school's page on {a['checked']} and again on {sa}"
                add(k, b, f, kind, x, y, basis, note, sb, sa)
                continue
            add(k, b, f, kind, x, y, basis, '', sb, sa)
    return ev


def moved_under(f, x, y, limit):
    """the same quantity, moved by less than `limit` as a share of the old value"""
    try:
        if f == 'fee':
            (cx, ax), (cy, ay) = x.split(' ', 1), y.split(' ', 1)
            if cx != cy:
                return False
            a, b = float(ax), float(ay)
        elif f == 'duration':
            a, b = float(x.split('|')[1]), float(y.split('|')[1])
        else:
            a, b = float(x), float(y)
        return a > 0 and abs(b - a) / a < limit
    except (ValueError, IndexError):
        return False


def read_state():
    p = HIST / 'state.csv'
    if not p.exists():
        return None
    return {(r['school_slug'], r['key']): r for r in csv.DictReader(open(p, encoding='utf-8'))}


def write_state(st):
    HIST.mkdir(parents=True, exist_ok=True)
    with open(HIST / 'state.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=STATE_COLS, quoting=csv.QUOTE_ALL, lineterminator='\n')
        w.writeheader()
        w.writerows(st[k] for k in sorted(st))


def keep_removed(old, events):
    """the last recorded details of every programme no longer listed"""
    gone = [e for e in events if e['field'] == 'listed' and e['kind'] == 'removed']
    if not gone:
        return
    p = HIST / 'removed.csv'
    new = not p.exists()
    with open(p, 'a', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['removed_on'] + STATE_COLS, quoting=csv.QUOTE_ALL, lineterminator='\n',
                           extrasaction='ignore')
        if new:
            w.writeheader()
        for e in gone:
            w.writerow(dict(old[(e['school_slug'], e['key'])], removed_on=e['date']))


def append_log(events, fresh=False):
    HIST.mkdir(parents=True, exist_ok=True)
    p = HIST / 'changes.csv'
    new = fresh or not p.exists()
    with open(p, 'w' if fresh else 'a', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=LOG_COLS, quoting=csv.QUOTE_ALL, lineterminator='\n')
        if new:
            w.writeheader()
        w.writerows(events)


def main():
    today = datetime.date.today().isoformat()
    cur = state_of(catalogue_rows())
    old = read_state()
    meta = HIST / 'last_run.txt'
    prev_run = meta.read_text().strip() if meta.exists() else ''
    if old is None:
        write_state(cur)
        append_log([])
        print('what changed: no recorded state; this run is the starting point')
        events = []
    else:
        carry_first_seen(old, cur)
        events = diff(old, cur, today, recheck_changes(), renames(), prev_run)
        if events:
            append_log(events)
            keep_removed(old, events)
        write_state(cur)
    meta.write_text(today + '\n')

    # each change with the dashboard programme it belongs to (programmes_tagged.csv)
    tagged = {}
    for r in csv.DictReader(open(R / 'programmes_tagged.csv', encoding='utf-8')):
        if r['theme'] != 'UNCLASSIFIED':
            tagged[(r['school_slug'], product_key(r['programme_name']))] = r
    # changes under a name later confirmed as renamed were the rename: leave them out
    old_names = set(renames())
    log = [e for e in csv.DictReader(open(HIST / 'changes.csv', encoding='utf-8'))
           if (e['school_slug'], e['key']) not in old_names]
    # a programme removed after its page was found gone was dropped by the school then, not
    # when we removed the row: the removal takes the dates of the likely-discontinued mark
    found_gone = {}
    for e in log:
        if e['field'] == 'status' and e['kind'] == 'discontinued':
            found_gone.setdefault((e['school_slug'], e['key']), (e.get('seen_before', ''), e.get('seen_after', '')))
    for e in log:
        k = (e['school_slug'], e['key'])
        if e['field'] == 'listed' and e['kind'] == 'removed' and k in found_gone:
            e['seen_before'], e['seen_after'] = found_gone[k]
    out = R / 'outputs' / 'what_changed.csv'
    cols = LOG_COLS + ['programme', 'tile']
    with open(out, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=cols, quoting=csv.QUOTE_ALL, lineterminator='\n')
        w.writeheader()
        for e in log:
            t = tagged.get((e['school_slug'], e['key']))
            partner = (t or {}).get('partner') or cur.get((e['school_slug'], e['key']), {}).get('partner', '')
            w.writerow(dict(e, programme=t['programme_name'] if t else '',
                            tile=('partner' if partner else 'own') if e['school_slug'] == 'isb' else ''))
    school = sum(1 for e in log if e['basis'] == 'school')
    print(f'what changed: {len(events)} changes recorded today; history holds {len(log)} since '
          f'{HISTORY_START} ({school} by schools, {len(log) - school} to our records)')


if __name__ == '__main__':
    main()
