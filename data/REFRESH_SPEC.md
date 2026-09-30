# Monthly gap-fill refresh (for the scheduled Claude task)

The GitHub Action recomputes everything from `data/catalogues/*.csv`. It cannot read
school websites. This task is the part that does, and it only fetches what is missing.

## Each month

1. Pull `main`. Run `python scripts/refresh_queue.py`. It writes `outputs/refresh_queue.csv`:
   one row per programme with a missing fee, format, duration or future start date, a
   team-sheet row no live page has confirmed, or a row not verified in 120 days. Rows are
   ordered ISB first, then Indian schools, global schools, platforms.
2. Work down the queue. For each row, open `url` and fill **only** the fields named in
   `fetch`, in that school's catalogue CSV. Do not touch other fields.
   - `fee` → `fee_raw` verbatim, `fee_currency`, `fee_amount` (number, no commas).
   - `format` → Campus | Blended | Live Online | Self-paced Online.
   - `duration` → `duration_raw` verbatim, plus `duration_days` (campus) or `duration_weeks`.
   - `next_start` → ISO date of the next cohort that has not started yet.
   - Set `last_verified` to today's date on every row you open, whether or not you changed it.
3. If the page is gone and the school's catalogue no longer lists the programme, delete the
   row. If you are unsure, leave it and write the reason in `source_note`.
4. New programmes on a school's catalogue page that we do not hold: add a row with
   `provenance=catalogue-capture` and today's `last_verified`.
5. Never invent a fee, date or topic. Blank beats a guess.
6. Commit to `main` as "Monthly gap-fill YYYY-MM". The push re-runs the Action, which
   rebuilds the dashboard and the drift check.

## Budget

Stop after 150 page fetches in one run and leave the rest of the queue for next month.
The queue is ordered so the programmes that matter most get filled first.

## Network

The environment running this task must be allowed to reach the schools' domains:
execed.isb.edu, online.isb.edu, exed.iima.ac.in, eep.iimb.ac.in, www.iimcal.ac.in,
iimidr.ac.in, iimk.ac.in, www.iiml.ac.in, executive-education.spjain.co.in, www.exed.hbs.edu,
www.hec.edu, www.imd.org, www.insead.edu, www.kellogg.northwestern.edu, www.london.edu,
www.gsb.stanford.edu, executiveeducation.wharton.upenn.edu, *.emeritus.org, timespro.com,
www.jaroeducation.com, imarticus.org.

## Importing a new version of the team's competitor sheet

    python scripts/import_team_sheet.py path/to/Competitor-Power_Bi_Sheet.xlsx

Matches are never overwritten, only blanks are filled. Check
`data/team_sheets/name_matches_to_review.csv` for name matches made on word overlap.
