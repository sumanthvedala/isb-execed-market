# Weekly refresh (for the Claude refresh session)

The GitHub Action runs every Monday and recomputes everything from `data/catalogues/*.csv`.
It cannot read school websites. This task is the part that does. It makes two passes, in
this order, and the refresh is not finished until both are done.

## Pass 1: fill what is missing

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
   row. If you are unsure, keep it: set `status` to `likely discontinued` and say why, with the
   date, in `status_note`; the dashboard marks it. Clear both if the programme turns out to be on sale.
4. New programmes on a school's catalogue page that we do not hold: add a row with
   `provenance=catalogue-capture` and today's `last_verified`.
5. Never invent a fee, date or topic. Blank beats a guess.

## Pass 2: make every name open the programme's own page

Pass 1 comes back with whatever link it met first, and a lot of those are launch articles,
course-listing sites, calendars or brochures. The dashboard links a programme's name only
to a programme page or a landing page, so a wrong link shows as no link at all. Pass 2 is
mandatory on every refresh, including the links pass 1 has just written.

1. Run `python scripts/link_audit.py`. It writes `outputs/link_queue.csv`: every programme, in
   the catalogues and in the launch register, with no programme page or landing page on
   record, worst first (news articles, listing sites, short links and broken links, then
   index pages, then programmes that hold only a brochure). `scripts/linkkind.py` is the
   rule it judges by.
2. For each row, find the programme's own page on the school's site or its delivery
   partner's (Emeritus, TimesPro, Jaro, Imarticus, upGrad, Simplilearn, Great Learning and
   the like). Start from the link held: a launch article usually links to the page; a
   calendar or index page lists it. Search the school's domain for the exact title if not.
3. Open the page you found. Write it only if it loads today and its title or heading names
   this programme. A different batch of the same programme is the same programme.
4. Where to write it:
   - Catalogue rows: the page goes in `url`, or in `landing_url` when the school or partner
     runs a separate landing page. A PDF that was sitting in `url` moves to `brochure_url`.
   - Launch register (`data/peer_launches.csv`): the page goes in `url`. The article,
     press release or brochure that evidences the launch stays in `source_url`. Never put
     a news article in `url`.
5. If the school publishes no page for the programme (some list only a calendar and a PDF),
   leave the brochure where it is and add a line to `data/link_checks.csv`
   (`school_slug, programme_name, checked_on, finding`). The audit then leaves that
   programme alone for 90 days.
6. Never write: news or press pages, blogs, course aggregators (Shiksha, Careers360 and
   the like), short links, sign-in links (SharePoint, OneDrive, Google Docs), or a school's
   home page, catalogue index or calendar.
7. Run `python scripts/link_audit.py` again. The count it prints must be lower than when you
   started, and it must show no `news`, `aggregator`, `shortener`, `private` or `broken`
   rows unless the changelog line says why each one is still there.

## Finish

1. Append one line to `data/changelog.csv` (date, scope isb|peers|data, headline, detail) saying
   what you filled, removed or added, and how many links pass 2 fixed and how many are still
   queued. It shows on the dashboard's Updates page. Programme adds, drops and repricing are
   detected automatically; do not log those by hand.
2. Commit to `main` as "Weekly gap-fill YYYY-MM-DD". The push re-runs the Action, which
   rebuilds the dashboard and the drift check.

## Budget

Stop pass 1 after 150 page fetches in one run and leave the rest of the queue for next week.
Keep 50 fetches back for pass 2: a wrong link on the page is worse than a blank fee.
Both queues are ordered so the programmes that matter most come first.

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
