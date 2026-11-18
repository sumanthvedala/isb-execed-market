#!/usr/bin/env python3
"""Applies confirmed programme renames to the catalogues.

A school sometimes renames a programme: the old page goes or forwards to a new
one, and most other details stay the same. Left alone, the catalogue then holds
the old name as a programme that looks discontinued and, often, the new name as
a second row, so the programme is counted twice or shown as gone.

data/renames.csv holds each decision: school_slug, old_name, new_name, decision
(renamed | not a rename), decided_on, evidence, decided_by. For every row
decided `renamed`:
  - if the catalogue already holds the new name, the old row is removed: the new
    row was captured from the live page and stands as it is;
  - otherwise the old row takes the new name, its likely-discontinued mark is
    cleared and the rename is noted in source_note.
Rows decided `not a rename` only stop scripts/rename_candidates.py from
proposing the pair again.

Runs on every build, before update_launches.py and classify.py, so a rename
also survives a re-import of the competitor sheet. Idempotent.
"""
import csv, pathlib, re, sys

R = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / 'scripts'))
from import_team_sheet import CAT_FIELDS  # noqa: E402

COLS = ['school_slug', 'old_name', 'new_name', 'decision', 'decided_on', 'evidence', 'decided_by']


def load():
    p = R / 'data' / 'renames.csv'
    return list(csv.DictReader(open(p, encoding='utf-8'))) if p.exists() else []


def norm(s):
    return re.sub(r'\s+', ' ', (s or '').strip()).lower()


def main():
    done = []
    by_school = {}
    for r in load():
        if norm(r['decision']) == 'renamed':
            by_school.setdefault(r['school_slug'], []).append(r)
    for slug, rn in by_school.items():
        path = R / 'data' / 'catalogues' / f'{slug}.csv'
        if not path.exists():
            continue
        with open(path, encoding='utf-8') as f:
            rd = csv.DictReader(f)
            fields = rd.fieldnames or CAT_FIELDS
            rows = list(rd)
        changed = False
        for r in rn:
            old = [x for x in rows if norm(x['programme_name']) == norm(r['old_name'])]
            if not old:
                continue
            has_new = any(norm(x['programme_name']) == norm(r['new_name']) for x in rows)
            if has_new:
                rows = [x for x in rows if x not in old]
                done.append(f"{slug}: removed '{r['old_name']}', now '{r['new_name']}'")
            else:
                for x in old:
                    x['programme_name'] = r['new_name']
                    x['status'] = ''
                    x['status_note'] = ''
                    note = f"renamed from '{r['old_name']}' ({r['decided_on']})"
                    x['source_note'] = (x.get('source_note', '') + '; ' + note).strip('; ')
                done.append(f"{slug}: '{r['old_name']}' renamed '{r['new_name']}'")
            changed = True
        if changed:
            with open(path, 'w', newline='', encoding='utf-8') as f:
                w = csv.DictWriter(f, fieldnames=fields, quoting=csv.QUOTE_ALL, extrasaction='ignore', lineterminator='\n')
                w.writeheader()
                w.writerows(rows)
    print(f'renames: {len(done)} applied' + (':\n  ' + '\n  '.join(done) if done else ''))


if __name__ == '__main__':
    main()
