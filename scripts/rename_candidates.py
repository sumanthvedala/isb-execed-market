#!/usr/bin/env python3
"""Programmes that look renamed rather than discontinued.

A rename shows up as an old programme whose page has gone or forwards elsewhere
(marked `likely discontinued`, or removed from the catalogue) while another
programme at the same school carries most of the same details. Each old
programme is scored against every live programme at its school:

  page forwards to it, or our note names it as the closest current programme  +4
  shared words in the name (Jaccard of the core words, x3)                    up to +3
  fee in the same currency within 15% (+2 if equal)                           +1.5
  duration within 15%                                                           +1
  same number of modules                                                        +1
  same format                                                                 +0.5
  same delivery partner                                                       +0.5
  same level                                                                  +0.3
  listed within 120 days of the old one going                                   +1

A pair is only scored when the old page forwards to the candidate, our note names
it, or the two names share at least a third of their core words: a school's short
programmes often share one fee, length and format, so details alone prove nothing.
For the same reason a matching fee, length or format counts for less the more of
the school's programmes share it (weight x (1 - share)).

Pairs already decided in data/renames.csv are skipped. A score of 6 or more is
high confidence, 4 or more medium, 3 or more low. The two best candidates per old
programme go to outputs/rename_candidates.csv, for the weekly refresh to confirm
on the schools' pages (data/REFRESH_SPEC.md) and record in data/renames.csv.
Nothing here changes the catalogue.
"""
import csv, glob, re, difflib, datetime, pathlib, sys

R = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / 'scripts'))
import import_team_sheet as its  # noqa: E402
from what_changed import product_key, weeks, num  # noqa: E402

TODAY = datetime.date.today()


def core(name):
    return its.core(its.norm_name(re.sub(r'\(.*?\)|\[.*?\]', ' ', name or '')))


def fee(r):
    a = num(r.get('fee_amount'))
    return ((r.get('fee_currency') or '').strip(), float(a)) if a else None


def named_successor(note):
    m = re.search(r'forwards to (?:the )?(.+?)(?: \(checked| list|$)', note or '') or \
        re.search(r'closest current programme: (.+?)\)', note or '')
    return m.group(1).strip() if m else ''


def score(o, c, listed_on, share):
    s, why, diff = 0.0, [], []
    succ = named_successor(o.get('status_note', ''))
    named = bool(succ) and difflib.SequenceMatcher(None, its.norm_name(succ), its.norm_name(c['programme_name'])).ratio() >= 0.8
    if named:
        s += 4
        why.append('old page forwards to it' if 'forwards' in o.get('status_note', '') else 'our note names it as the successor')
    a, b = core(o['programme_name']), core(c['programme_name'])
    j = len(a & b) / len(a | b) if a and b else 0
    if not named and j < 0.33:
        return 0, [], []
    s += 3 * j
    if j >= 0.33:
        why.append(f'name {int(round(100 * j))}% the same words')
    sl = c['school_slug']
    fo, fc = fee(o), fee(c)
    if fo and fc and fo[0] == fc[0]:
        rare = 1 - share(sl, 'fee', fc)
        if abs(fo[1] - fc[1]) < 0.5:
            s += 2 * rare; why.append('same fee')
        elif abs(fo[1] - fc[1]) <= 0.15 * max(fo[1], fc[1]):
            s += 1.5 * rare; why.append('fee within 15%')
        else:
            diff.append('fee differs')
    wo, wc = num(weeks(o)), num(weeks(c))
    if wo and wc:
        if abs(float(wo) - float(wc)) <= 0.15 * max(float(wo), float(wc)):
            s += 1 * (1 - share(sl, 'weeks', wc)); why.append('same length')
        else:
            diff.append('length differs')
    mo, mc = num(o.get('total_modules')), num(c.get('total_modules'))
    if mo and mc:
        if mo == mc:
            s += 1; why.append(f'{mo} modules each')
        else:
            diff.append('modules differ')
    for f, pts, lab in (('format', .5, 'same format'), ('partner', .5, 'same partner'), ('level', .3, 'same level')):
        x, y = (o.get(f) or '').strip(), (c.get(f) or '').strip()
        if x and y and x not in ('Unknown',):
            if x == y:
                s += pts * (1 - share(sl, f, y)); why.append(lab)
            elif f == 'format':
                diff.append(f'format {x} vs {y}')
    gone = o.get('_gone_on', '')
    if gone and listed_on.get((c['school_slug'], product_key(c['programme_name']))):
        d = listed_on[(c['school_slug'], product_key(c['programme_name']))]
        if abs((datetime.date.fromisoformat(d) - datetime.date.fromisoformat(gone)).days) <= 120:
            s += 1; why.append('listed around when the old one went')
    return round(s, 2), why, diff


def main():
    rows = [r for f in sorted(glob.glob(str(R / 'data' / 'catalogues' / '*.csv')))
            for r in csv.DictReader(open(f, encoding='utf-8')) if (r.get('programme_name') or '').strip()]
    hist = R / 'data' / 'history'
    log = list(csv.DictReader(open(hist / 'changes.csv', encoding='utf-8'))) if (hist / 'changes.csv').exists() else []
    listed_on = {(e['school_slug'], e['key']): e['date'] for e in log if e['field'] == 'listed' and e['kind'] == 'added'}
    gone_on = {(e['school_slug'], e['key']): e['date'] for e in log if e['field'] == 'status' and e['kind'] == 'discontinued'}
    # old programmes: still listed but marked likely discontinued, or removed in the last year
    old = []
    for r in rows:
        if (r.get('status') or '').strip():
            r['_gone_on'] = gone_on.get((r['school_slug'], product_key(r['programme_name'])), '')
            old.append(r)
    removed = hist / 'removed.csv'
    if removed.exists():
        cut = (TODAY - datetime.timedelta(days=365)).isoformat()
        for r in csv.DictReader(open(removed, encoding='utf-8')):
            if r.get('removed_on', '') >= cut:
                r['_gone_on'] = r['removed_on']
                r['status_note'] = r.get('status_note') or f"no longer in the catalogue ({r['removed_on']})"
                old.append(r)
    decided = set()
    p = R / 'data' / 'renames.csv'
    if p.exists():
        for d in csv.DictReader(open(p, encoding='utf-8')):
            decided.add((d['school_slug'], its.norm_name(d['old_name']), its.norm_name(d['new_name'])))
    live = [r for r in rows if not (r.get('status') or '').strip()]
    # how common a value is at a school: a fee or length most programmes share proves little
    from collections import Counter
    tally, size = Counter(), Counter()
    for r in rows:
        size[r['school_slug']] += 1
        for f, v in (('fee', fee(r)), ('weeks', num(weeks(r))), ('format', r.get('format')), ('partner', r.get('partner')), ('level', r.get('level'))):
            if v:
                tally[(r['school_slug'], f, v)] += 1
    share = lambda sl, f, v: tally[(sl, f, v)] / size[sl] if size[sl] else 0
    out = []
    for o in old:
        cands = []
        for c in live:
            if c['school_slug'] != o['school_slug'] or product_key(c['programme_name']) == product_key(o['programme_name']):
                continue
            if (o['school_slug'], its.norm_name(o['programme_name']), its.norm_name(c['programme_name'])) in decided:
                continue
            s, why, diff = score(o, c, listed_on, share)
            if s >= 3:
                cands.append((s, c, why, diff))
        for s, c, why, diff in sorted(cands, key=lambda x: -x[0])[:2]:
            out.append(dict(school_slug=o['school_slug'], old_name=o['programme_name'], new_name=c['programme_name'],
                            score=s, confidence='high' if s >= 6 else 'medium' if s >= 4 else 'low',
                            matches='; '.join(why), differs='; '.join(diff), old_note=o.get('status_note', ''),
                            old_page=o.get('url', ''), new_page=c.get('landing_url') or c.get('url', '')))
    out.sort(key=lambda x: (-x['score'], x['school_slug']))
    cols = ['school_slug', 'old_name', 'new_name', 'score', 'confidence', 'matches', 'differs', 'old_note', 'old_page', 'new_page']
    with open(R / 'outputs' / 'rename_candidates.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=cols, quoting=csv.QUOTE_ALL, lineterminator='\n')
        w.writeheader()
        w.writerows(out)
    hi = sum(1 for x in out if x['confidence'] == 'high')
    print(f'rename candidates: {len(out)} pairs for {len({(x["school_slug"], x["old_name"]) for x in out})} '
          f'programmes that look gone ({hi} high confidence) -> outputs/rename_candidates.csv')


if __name__ == '__main__':
    main()
