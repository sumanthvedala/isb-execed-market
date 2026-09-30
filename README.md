# ISB Exec Ed Market Map — live dashboard

Static dashboard + a monthly refresh. No server, no licence, no database.

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

## What runs each month

`build_taxonomy.py` → `classify.py` → `analyse.py` → `demand_index.py` → `refresh_queue.py` → `build_data.py`
→ `build_site.py` → `check_drift.py`

`check_drift.py` fails the build if any school's product count moved more than 10%, so a
broken scraper cannot silently rewrite the numbers.

## The two files a human edits

| File | What it does |
| --- | --- |
| `data/overrides.csv` | Pins a product to the right topic. All 46 ISB products are pinned here, hand-verified. Add a row and the fix is permanent. |
| `data/taxonomy.csv` | The 15 themes / 46 sub-themes / 230 topics and the keywords that match them. Edit via `scripts/build_taxonomy.py`. |

Both are editable in the GitHub web UI. Every edit is a commit with your name on it, which
is the audit trail.

`refresh_queue.py` writes `outputs/refresh_queue.csv`: only the programmes with a missing
fee, format, duration or future start date, or a row nobody has confirmed on a live page.
A scheduled Claude task works through it (`data/REFRESH_SPEC.md`) and commits the fixes;
that push re-runs the Action.

## Still to build

`data/catalogues/*.csv` are current snapshots, not live scrapers. Five of the eleven sites
(INSEAD, the LBS finder, IMD's programme finder, TimesPro, egmp.iiml.ac.in) need a headless
browser. Add Playwright scrapers under `scripts/scrape_*.py` and a
`- run: playwright install chromium` step. Until then the refresh recomputes from the
committed snapshots — everything downstream is live, the capture is not.

Scraping competitor sites monthly on a schedule is a decision someone senior should take
knowingly. GitHub runners use shared IPs, which sidesteps attribution but not the question.
