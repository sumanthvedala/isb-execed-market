# ISB Exec Ed Market Map: live dashboard

Static dashboard + a weekly refresh. No server, no licence, no database.

## Get it live in ~15 minutes

1. Create an **empty private repo** on GitHub named `isb-execed-theme-map`.
2. Push this folder:
   ```bash
   git init && git add -A && git commit -m "Initial theme map"
   git branch -M main
   git remote add origin https://github.com/<you>/isb-execed-theme-map.git
   git push -u origin main
   ```
3. **Settings → Pages → Source: GitHub Actions.**
4. **Actions tab → Refresh theme map → Run workflow.** It builds and deploys.
5. Your URL: `https://<you>.github.io/isb-execed-theme-map/`

> A **private** repo needs GitHub Team or Enterprise for Pages. On the free plan Pages
> is public, meaning anyone with the URL can read it. Everything in this repo is scraped
> from public catalogues, so that is a judgement call, not a breach — but **never commit
> ISB enrolment, revenue or feedback data.** Join those in Power BI inside the tenant.

## To gate it to isb.edu only (recommended)

Use **Azure Static Web Apps** with Entra ID sign-in instead of Pages. Same repo, same
Action; swap the deploy step for `Azure/static-web-apps-deploy@v1` and add a
`staticwebapp.config.json` requiring authentication. ISB is already on Microsoft 365, so
people sign in with the account they have and nobody outside the tenant gets in.

## What is in it

ISB against 15 schools (IIM-A, B, C, I, K, L, SP Jain; HBS, HEC, IMD, INSEAD, Kellogg, LBS,
Stanford, Wharton) and 4 platforms (Emeritus, Imarticus, Jaro, TimesPro), listed in
`data/schools.csv`. A platform listing carrying a school's brand is counted under the
school, with the platform as partner. Coursera and edX courses are out of scope.

The team's competitor sheet (the Power BI source) is merged in with
`scripts/import_team_sheet.py`; see `data/REFRESH_SPEC.md`.

## What runs each week

Every Monday at 02:00 UTC, and on any push that touches the data or scripts:

`build_taxonomy.py` → `apply_renames.py` → `classify.py` → `analyse.py` → `demand_index.py` → `refresh_queue.py` → `link_audit.py`
→ `what_changed.py` → `rename_candidates.py` → `build_data.py` → `build_site.py` → `check_drift.py`

`check_drift.py` fails the build if any school's product count moved more than 10% against
last month's snapshot, so a broken capture cannot silently rewrite the numbers. Changes on
What changed is measured over whatever period the reader picks, from the change history.

## What the dashboard shows

Search across every programme; a tab each for Indian schools and global schools, with one
tile per school that opens its whole portfolio (CXO programmes first, then blended, live
online, campus, self-paced) under the same filters as the search page; new launches by
other schools, by theme and level; a test for a programme idea; and What changed.

What changed shows, school by school, what moved over a period the reader picks (last week,
two weeks, month, quarter, six months or year), under an Indian and a Global button, in the
same tile layout as the schools tabs. Each tile gives the count of programmes changed, a
sentence saying what the school did, counts by kind (new programmes, gone or likely
discontinued, fees raised and cut with the median move, duration, modules, format, topics
taught) and the three changes worth seeing first. A school's page lists every change with
the value before in the body colour, the value after in red, and the size of the change.
`scripts/what_changed.py` compares the catalogues with the last run on every build and logs
what moved, dated, to `data/history/changes.csv` (history from 30 Sep 2026, rebuilt from the
repository by `scripts/backfill_history.py`). A change counts as the school's only when the
weekly re-check logged that programme as changed (`data/recheck_log.csv`), or when a
programme is newly listed or gone; a value we filled in or corrected is ours and hidden
unless the reader includes corrections. Pass 3 of the weekly refresh re-reads half of all
programmes each week (`scripts/recheck_queue.py`: IIMs first, then the global schools, then
SP Jain, then ISB and the platforms). The hand-written log sits at the bottom of the tab.

Renamed programmes: when a school renames a programme, the old name reads as discontinued
and the new one as a second programme. `scripts/rename_candidates.py` scores every programme
that looks gone against the live programmes at its school (old page forwarding to it, shared
name words, matching fee, length, modules, format, partner and level) and writes
`outputs/rename_candidates.csv`; pass 4 of the weekly refresh confirms each on the school's own
pages and records the decision in `data/renames.csv`. `scripts/apply_renames.py` applies the
confirmed ones on every build, and What changed shows them as renamed.

Every programme has one programme type, so nothing is counted twice: C-suite (named for a
C-suite role, or filed under C-suite by the school, whatever its format), Blended, Live
online (12 weeks or more online), TFP campus and TFP online (topic-focused programmes, ISB's
term: up to two weeks on campus or under 12 weeks online), Long campus, Self-paced. Tiles and
school pages give the median fee per type. ISB has two tiles: in-house and with partners.
Fee comparisons for a programme idea, and for ISB against its peers, use Indian programmes
only. The rules are in `scripts/build_data.py`.

## Links

A programme's name opens its landing page, else its page in the school's catalogue, else
its brochure. It never opens a news article, a course-listing site, a calendar or a short
link: `scripts/linkkind.py` judges every link from its URL, and `scripts/link_audit.py`
writes `outputs/link_queue.csv`, the list the refresh's second pass works through
(`data/REFRESH_SPEC.md`).

## Brand

Colours are the ISB colour sheet (`Colour_palette.pdf`, ISB page): Legacy Blue `#192890`,
Innovation Blue `#245bff`, Future Green `#80edd9`, Ivory `#f4f8fa`, the three grays
(`#e6ebee`, `#95a9b4`, `#5d6f7a`, `#2e3b42`). Spirited Coral and Uplift Yellow from the PGP
page mark warnings only. Shape follows silverjubilee.isb.edu. The sheet's printed hex and RGB
disagree on three colours by a few units (Innovation Blue, State Gray, Light Gray); the page
uses the hex.

Type: Inter (variable "Inter V", SIL Open Font License) for text and Reckless (Displaay,
variable) for headings, both served from `site/fonts/` as WOFF2, so the page calls no font
host except Google Fonts for the Newsreader fallback. `build_site.py` reads whatever
Reckless and Inter files are in that folder. It ignores macOS `._` stubs and any file with
"trial" in its name: a foundry's trial font is for evaluation, not a public website.

Logos are in `site/brand/`: the white ISB Executive Education lockup in the masthead, and
the colour one for light backgrounds. The ISB 25 mark is not used here.

This repo and its Pages site are public. Anyone can download the font files from either.
Check that ISB's Reckless licence covers that.

## The two files a human edits

| File | What it does |
| --- | --- |
| `data/overrides.csv` | Pins a product to the right topic. All 46 ISB products are pinned here, hand-verified. Add a row and the fix is permanent. |
| `data/taxonomy.csv` | The 15 themes / 46 sub-themes / 230 topics and the keywords that match them. Edit via `scripts/build_taxonomy.py`. |

Both are editable in the GitHub web UI. Every edit is a commit with your name on it, which
is the audit trail.

`refresh_queue.py` writes `outputs/refresh_queue.csv`: only the programmes with a missing
fee, format, duration or future start date, or a row nobody has confirmed on a live page.
A Claude refresh session works through it, then through `outputs/link_queue.csv`
(`data/REFRESH_SPEC.md`), and commits the fixes; that push re-runs the Action.

## Still to build

`data/catalogues/*.csv` are current snapshots, not live scrapers. Five of the eleven sites
(INSEAD, the LBS finder, IMD's programme finder, TimesPro, egmp.iiml.ac.in) need a headless
browser. Add Playwright scrapers under `scripts/scrape_*.py` and a
`- run: playwright install chromium` step. Until then the refresh recomputes from the
committed snapshots — everything downstream is live, the capture is not.

Scraping competitor sites weekly on a schedule is a decision someone senior should take
knowingly. GitHub runners use shared IPs, which sidesteps attribution but not the question.
