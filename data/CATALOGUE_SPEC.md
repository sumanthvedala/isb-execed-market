# Catalogue capture spec (shared by all catalogue agents)

Snapshot date: 2026-09-24. Scope: OPEN-ENROLMENT executive education only (anything an individual or company can buy off a public catalogue). Exclude degree programmes (MBA, EMBA, PhD, PGP, PGPX, MBA-equivalent 1-yr programmes), custom/company-specific programmes, and events/conferences.
INCLUDE: campus short programmes, long general-management / leadership programmes, live-online certificate programmes, blended programmes, self-paced online courses sold under the school's name, and partner-delivered programmes (Emeritus, Jaro, TimesPro, upGrad, Imarticus, Coursera, GetSmarter, etc.) sold under the school's brand. Mark the partner.

Network note: the shell (Bash/curl/python requests) CANNOT reach external websites — egress is blocked. Use WebFetch and WebSearch only. WebFetch summarises pages through a small model, so always ask it to "list EVERY programme on this page as a table with ... do not summarise or skip any". Paginated/filtered finders: fetch each page/category separately. If a site exposes a JSON search/listing endpoint, try fetching it with WebFetch.

Write ONE CSV per school to /home/claude/research/catalogues/<school_slug>.csv (UTF-8, comma separated, quote every field) with EXACTLY these columns:

school, school_slug, region (India|Global), programme_name, url, school_category (the school's own topic/category label, verbatim; semicolon-separate if several), format (Campus|Live Online|Blended|Self-paced Online|Unknown), duration_raw (verbatim), duration_days (numeric estimate of contact days for campus; blank if not derivable), duration_weeks (numeric for online/blended; blank if n/a), fee_raw (verbatim incl. currency/GST notes), fee_currency (INR|USD|EUR|GBP|CHF|SGD|other), fee_amount (numeric, no commas; blank if not published), level (C-suite/Senior|Mid-career|Early/Emerging|Functional specialist|Board|Mixed|Unknown), partner (blank if school-delivered), target_audience (<=200 chars, verbatim-ish), key_topics (semicolon list of 4-12 concrete topics taught, from the page), is_new_2025_26 (Y if the page/news marks it new or first cohort is 2025/2026, else blank), next_start (verbatim date if shown), source_note (how you got it: page fetched / search snippet / inferred)

Rules
- Never invent a fee, date or topic. Blank beats a guess. If you only saw a programme in a search snippet, still include it but put "search snippet" in source_note.
- key_topics must come from the page's own curriculum/modules/"key topics" text, not your assumptions.
- Aim for completeness of the catalogue over depth per programme: a row with name+url+category+format is better than a missing row.
- Also write /home/claude/research/catalogues/<school_slug>_notes.md: total count, how the school organises its catalogue (its own taxonomy labels and counts per label), what looks newly launched or heavily expanded (their "bets"), anything that failed to fetch, and URLs used.

Return to the caller: a <=250-word summary: count by format, count by school_category, 3-5 observations about where the school is concentrating (front-loading), and any gaps in capture.
