# Weekly refresh (for the Claude refresh session)

The GitHub Action runs every Monday and recomputes everything from `data/catalogues/*.csv`.
It cannot read school websites. This task is the part that does. It makes five passes, in
this order, and the refresh is not finished until all are done.

## Pass 0: find programmes we do not hold yet

The dashboard can only show programmes that are in the catalogues, so every refresh starts here.

1. For each school in `data/catalogue_index.csv`, open its listing pages (programme finder, calendar,
   "all programmes" page). Where a school has no listing recorded, find it and add it to the file.
2. Compare what is listed with the school's catalogue CSV. For each programme we do not hold, add a row
   with `provenance=catalogue-capture` and today's `last_verified`, filled from its own page by the format
   rules in `data/CATALOGUE_SPEC.md`. Set `is_new_2025_26` to Y if the page says it is new or announces its
   first cohort.
3. A listed programme we already hold under a slightly different name is the same programme: update its
   name only if the school has renamed it, and say so in `source_note`.
4. Up to 40 fetches. Record `last_checked` for each listing you opened.

## Pass 1: fill what is missing

1. Pull `main`. Run `python scripts/refresh_queue.py`. It writes `outputs/refresh_queue.csv`:
   one row per programme with a missing fee, format, duration or future start date, a
   team-sheet row no live page has confirmed, or a row not verified in 120 days. Rows are
   ordered ISB first, then Indian schools, global schools, platforms.
2. Work down the queue. For each row, open `url` and fill **only** the fields named in
   `fetch`, in that school's catalogue CSV. Do not touch other fields.
   - `fee` → `fee_raw` verbatim, `fee_currency`, `fee_amount` (number, no commas).
   - `format` → Campus | Blended | Live Online | Online | Self-paced Online, by the format rules in
     data/CATALOGUE_SPEC.md. A cohort course with weekly deadlines is Online, never Self-paced. ISB rows take
     ISB's own label from its page; ISB runs no self-paced programmes.
   - For a new programme, read the format from its page, not from the school's listing card.
   - `duration` → `duration_raw` verbatim, plus `duration_days` (campus) or `duration_weeks`.
   - `next_start` → ISO date of the next cohort that has not started yet.
   - Set `last_verified` to today's date on every row you open, whether or not you changed it.
3. A page that is gone or forwards elsewhere may be a rename, not a programme withdrawn: check
   `outputs/rename_candidates.csv` for it first and settle it in pass 4. If it is not a rename and
   the page is gone and the school's catalogue no longer lists the programme, delete the
   row. If you are unsure, keep it: set `status` to `likely discontinued` and say why, with the
   date, in `status_note`; the dashboard marks it. Clear both if the programme turns out to be on sale.
4. New programmes on a school's catalogue page that we do not hold: add a row with
   `provenance=catalogue-capture` and today's `last_verified`.
5. New launches are recorded automatically. For every programme you add in Pass 0, and any you open
   here, set `is_new_2025_26` to Y when its page says it is new, announces its first cohort, or the school
   has announced it. `scripts/update_launches.py` then adds it to `data/peer_launches.csv` on the next
   build, dated by the day it was first seen, and it appears under New launches. If you find the
   announcement date, add it to `status_note`.
6. Never invent a fee, date or topic. Blank beats a guess.

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

## Pass 3: re-check what we already hold

The What changed tab can only show a school raising a fee, adding modules or changing a
programme's length if someone re-reads the page. This pass does that for half of all
programmes each week, so every programme is re-read every two weeks.

1. Run `python scripts/recheck_queue.py`. It writes `outputs/recheck_queue.csv`: this week's half,
   never-checked and longest-unchecked first, in this order: IIM Ahmedabad, Bangalore, Calcutta,
   Indore, Kozhikode, Lucknow, then the global schools alphabetically, then SP Jain, then ISB and
   the platforms.
2. For each row, open `page` (or find the programme's page as in pass 2) and read the current fee,
   duration, number of modules, format, topics taught and next start. Where a school publishes a
   calendar or fee table covering many programmes (IIM-K, IIM-L), read it once for all its rows.
3. Where the page differs from the catalogue row, update the row: `fee_raw`, `fee_currency`,
   `fee_amount`; `duration_raw` with `duration_days` or `duration_weeks`; `total_modules`; `format`
   by the format rules in `data/CATALOGUE_SPEC.md`; `key_topics`; `next_start`. Set `last_verified`
   to today on every row you open.
4. Add one line per programme to `data/recheck_log.csv`, changed or not:
   `checked_on` (today), `school_slug`, `programme_name` (exactly as in the catalogue), `outcome`
   (`same`, `changed`, `page gone` or `unreachable`), `fields` (for `changed`: the fields that moved,
   separated by semicolons, from `fee`, `duration`, `modules`, `format`, `topics`, `next_start`,
   `level`, `partner`), `page` (the page you read) and `note` (anything a reader should know, such as
   "early-bird fee now shown"). This line is what marks a change as the school's on the What changed
   tab; a change without it shows as a correction to our record.
5. A page that is gone: follow Pass 1 step 3 (mark `likely discontinued`, or delete the row if the
   school's catalogue no longer lists it) and log `page gone`.
6. A row that is also in the pass 1 queue: fill and re-check it in one visit.
7. Never record a change you have not seen on the school's own page or its delivery partner's.
   A fee that differs only because one source quotes it with GST and the other without is not a
   change: keep the row as it is and say so in `note`.

## Pass 4: confirm renames

Schools rename programmes. The old page goes or forwards to a new one and most details stay
the same; left alone, the old name reads as discontinued and the new one as a second programme.

1. Run `python scripts/rename_candidates.py`. It writes `outputs/rename_candidates.csv`: each
   programme that looks gone (marked `likely discontinued`, or removed in the last year) with up
   to two live programmes at the same school that could be its new name, scored on whether the old
   page forwards to it, shared words in the name, and matching fee, length, modules, format,
   partner and level. Work down it, high confidence first.
2. Confirm a rename only on the school's or its partner's own evidence: the old page forwards to
   the new one; the school says so ("formerly", "previously known as", "now called"); or the old
   and new brochures or pages show the same programme (same director, same modules or structure)
   under a new name. A likeness of name, fee or length alone is not enough.
3. Record every decision in `data/renames.csv`, one line per pair: `school_slug`, `old_name` and
   `new_name` exactly as in the catalogue, `decision` (`renamed` or `not a rename`), `decided_on`
   (today), `evidence` (what you saw, with the page), `decided_by` ("weekly refresh"). A `not a
   rename` line stops the pair being proposed again.
4. Do not edit the catalogue for a rename. `scripts/apply_renames.py` runs on every build: it
   removes the old row when the new name is already held, or gives the old row the new name and
   clears its likely-discontinued mark, and What changed shows the programme as renamed.
5. ISB's own renames come from the Product & Content Strategy team and are already recorded;
   do not override them.

## Finish

1. Append one line to `data/changelog.csv` (date, scope isb|peers|data, headline, detail) saying
   what you filled, removed or added, and how many links pass 2 fixed and how many are still
   queued, and how many programmes pass 3 re-checked and found changed. It shows in the Log on the
   dashboard's What changed tab. Programme adds, drops and repricing are detected automatically
   (scripts/what_changed.py); do not log those by hand.
2. Commit to `main` as "Weekly gap-fill YYYY-MM-DD". The push re-runs the Action, which
   rebuilds the dashboard and the drift check.

## Budget

Spend up to 40 fetches on pass 0. Stop pass 1 after 150 page fetches in one run and leave the rest of the queue for next week.
Keep 50 fetches back for pass 2: a wrong link on the page is worse than a blank fee.
Pass 3 has its own budget: work down the whole re-check queue. If the session runs out of time,
stop where you are; the rows not reached stay at the top of next week's queue.
Every queue is ordered so the programmes that matter most come first.

## How pass 2 was done the first time (17 Nov 2026), so it can be repeated

- The shell reaches most school sites through the session's proxy: `curl -sSL -A "Mozilla/5.0 ..."` worked for
  iimk.ac.in, iiml.ac.in, london.edu, imarticus.org, exed.iima.ac.in and emeritus.org. www.isb.edu and
  execed.isb.edu return 403; use search results for those. Talentedge pages return 530 and cannot be checked.
- IIM-K and IIM-L publish a calendar and a brochure PDF per short programme, not a page. Parse the calendar
  (IIM-K: `/academic-programmes/OPEN-MDP/course-calender`, `E-MDP`, `A-MDP`; IIM-L: `/admission/mdp/mdpCalendar`),
  match each row's name to the programme name exactly once batch numbers and filler words are dropped, and fill
  `brochure_url` only on an exact match. A looser match linked a CPO programme to a CPAIO brochure.
- For one-offs, search for the title, then fetch the candidate and check that its `<title>` or `<h1>` names the
  programme before writing it. Guessing an address that happens to return 200 is not verification.
- A programme that is on a school's calendar with no brochure and no page is a dead end, not a gap: log it.

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
