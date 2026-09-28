# Demand evidence capture spec

Goal: strengthen the demand evidence behind an ISB Executive Education theme/sub-theme/topic study,
for the period **2027-2031**. Snapshot date 26 Sep 2026.

Read `/home/claude/research/demand2/TOPIC_LIST.txt` first: 223 topics under 15 themes / 46 sub-themes.
Map every signal you capture to the closest `topic_id`. If nothing fits, put `topic_id` blank and
name the concept in `skill_or_topic_verbatim` — a missing topic is itself a finding.

NETWORK: the shell cannot reach the web. Use WebSearch and WebFetch only.
BUDGET: roughly 30 web calls. Prefer one rich source over three thin ones.

## Rules that matter more than volume
- **Never invent a number.** Every row needs `source`, `source_url`, `pub_date` and a
  `metric_verbatim` that is quoted or closely paraphrased from the source. If you only have a search
  snippet and could not open the page, write `snippet-only` in `evidence_grade`.
- **Separate what the source says from what you infer.** The `metric_verbatim` column is the source's
  words. Your reading goes in `note`.
- **Prefer behaviour over stated intent.** A job-posting count or a regulatory obligation outranks a
  survey of what executives say they plan to do. Record which it is in `signal_type`.
- **Seniority matters.** This study is about programmes for managers and senior leaders. A signal
  about entry-level demand for a technical skill is weak evidence here. Mark `seniority` honestly.
- **Contradictions are signal.** If two credible sources disagree, record both rows and say so.

## Output
Append rows to `/home/claude/research/demand2/<your-slug>.csv` with EXACTLY these columns:

signal_id, topic_id, skill_or_topic_verbatim, source, source_url, pub_date, geography
(India|US|Europe|Global), signal_type (job postings|employer survey|policy/regulation|industry body|
consultancy research|learner platform|expert/HBR|news), metric_verbatim, direction
(rising|stable|declining), horizon (now|2027-2029|2030+), seniority (Senior|Mid|All|Entry|Unknown),
evidence_grade (opened-page|snippet-only), note

Also write `<your-slug>_notes.md`: the 10-15 strongest findings in plain sentences, what surprised
you, what you could not verify, and a list of every URL you actually opened.

Return a <=350-word summary: the topics with the strongest new evidence, anything that contradicts
the idea that AI-adoption and AI-governance skills are the biggest 2027-2031 gap, and any topic the
taxonomy is missing.
