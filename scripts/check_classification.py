#!/usr/bin/env python3
"""Fails the build when the classifier files a programme under the wrong theme.

Run after scripts/classify.py. Four checks; the first three stop the build:
  1. data/classification_checks.csv: programmes whose theme (and topic, where given)
     was settled by hand. Add a row whenever a misfiled programme is fixed, so it
     cannot come back. A programme no longer in the catalogues is reported, not failed.
  2. TITLES below: made-up titles that pin each rule, so the rules hold for programmes
     no school has launched yet.
  3. Every programme whose subject is AI is filed under AI, Data & Digital unless it is
     AI applied to a function (marketing, HR, finance, supply chain ...), filed by hand,
     or about leading people with AI ("Leading Teams in the AI Era"). This is the IIMB GenAI
     and Agentic AI case.
  4. outputs/classification_review.csv lists what a person should look at: programmes
     filed on a broad keyword, and hand overrides the rules now disagree with.
"""
import csv, re, sys, pathlib, collections
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from classifier import Classifier, compile_kw, parse_title, norm, SKILL_THEMES, AI_THEME, _AI_TITLE, PEOPLE_WORDS

R = pathlib.Path(__file__).resolve().parent.parent
CL = Classifier(R)
AI = AI_THEME

# (title, expected theme, expected topic or '')
TITLES = [
    ("Generative AI and Agentic AI with Business Applications", AI, ""),
    ("Agentic AI for Leaders", AI, "Agentic AI and autonomous workflows"),
    ("Leading with Agentic AI", AI, "Agentic AI and autonomous workflows"),
    ("Executive Programme in Generative AI for Managers", AI, "Generative AI foundations and prompting"),
    ("AI for Managers", AI, ""),
    ("Post Graduate Certificate Programme in Machine Learning and AI", AI, ""),
    ("AI Strategy for Business Leaders", AI, "AI strategy for the enterprise"),
    ("Chief AI Officer Programme", AI, "AI strategy for the enterprise"),
    ("Responsible AI and AI Governance for Boards", "", ""),          # board or AI governance: either is fine
    ("Data Science for Business Decisions", AI, "Data science and applied statistics for managers"),
    ("Applied Business Analytics", AI, ""),
    ("AI in Marketing", "Marketing, Sales & Customer", "Generative AI for marketing and creative"),
    ("AI for HR Leaders", "People, Talent & Organisation", "AI in HR: hiring, development and productivity"),
    ("Supply Chain Analytics with AI", "Operations, Supply Chain & Quality", "AI and digital in supply chain"),
    ("General Management Programme in the Age of AI", "General Management (Integrative)", ""),
    ("Corporate Governance in the Age of AI", "Governance, Risk & Legal", ""),
    ("Leading Teams in the AI Era", "Leadership & Executive Capability", ""),
    ("Advanced Management Programme", "General Management (Integrative)", ""),
    ("Advanced Management Programme in Fintech", "Finance & Accounting", "Fintech, digital payments and embedded finance"),
    ("Finance for Non-Finance Executives", "Finance & Accounting", "Finance for non-finance managers"),
    ("Chief Financial Officer Programme", "Finance & Accounting", "Corporate finance and capital allocation"),
    ("Chief Human Resources Officer Programme", "People, Talent & Organisation", "CHRO and HR leadership"),
    ("Strategic Negotiations: Dealmaking for the Long Term", "Marketing, Sales & Customer", "Negotiation for commercial outcomes"),
    ("The Business of Entertainment, Media, and Sports", "Sector-Specific Management", ""),
    ("Sustaining Competitive Advantage", "Strategy", "Competitive strategy and advantage"),
    ("Executive Programme in Digital Marketing (Asynchronous)", "Marketing, Sales & Customer", "Digital marketing and performance media"),
    ("Family Business Management", "Innovation & Entrepreneurship", "Family business succession and next-generation owners"),
    ("Women in Leadership", "People, Talent & Organisation", "Women's leadership and gender in the workplace"),
    ("Design Thinking for Innovation", "Innovation & Entrepreneurship", "Design thinking and human-centred design"),
    ("ESG Reporting and Disclosure", "Sustainability, ESG & Climate", ""),
    ("Hospital Management", "Healthcare & Life Sciences", ""),
    ("Leadership Communication", "Personal Effectiveness & Communication", ""),
]
# (keyword, text it must NOT match): whole words only
NO_MATCH = [("ai strategy", "maintain strategy"), ("ports?", "sports"), ("erm", "long term"), ("chro", "asynchronous"),
            ("ott", "bottlenecks"), ("sme", "msme"), ("lean", "clean energy"), ("ai.*marketing", "sustainable marketing"),
            ("securities industry", "cyber security"), ("story", "history"), ("cx", "cxo"), ("eq", "equity")]

fails, notes = [], []

# 1. hand-settled programmes
tagged = {(r['school_slug'], r['programme_name']): r for r in csv.DictReader(open(R / 'programmes_tagged.csv', encoding='utf-8'))}
for c in csv.DictReader(open(R / 'data' / 'classification_checks.csv', encoding='utf-8')):
    r = tagged.get((c['school_slug'], c['programme_name']))
    if not r:
        notes.append(f"no longer in the catalogues: {c['school_slug']} | {c['programme_name']}")
        continue
    if r['theme'] != c['expected_theme'] or (c['expected_topic'] and r['topic'] != c['expected_topic']):
        fails.append(f"{c['school_slug']} | {c['programme_name']}: filed {r['theme']} / {r['topic']}, "
                     f"expected {c['expected_theme']}{' / ' + c['expected_topic'] if c['expected_topic'] else ''} ({r['match_why']})")

# 2. made-up titles
for title, th, tp in TITLES:
    got = CL.classify({'programme_name': title, 'school_slug': '_test'})
    t = CL.T.get(got['topic_id'], {})
    if (th and t.get('theme') != th) or (tp and t.get('topic') != tp):
        fails.append(f"rule test '{title}': filed {t.get('theme')} / {t.get('topic')}, expected {th}{' / ' + tp if tp else ''}")
for kw, text in NO_MATCH:
    if compile_kw(kw).search(norm(text)):
        fails.append(f"keyword '{kw}' matches inside '{text}'")

# 3. AI programmes outside the AI theme
for (sl, name), r in tagged.items():
    if r['theme'] in ('UNCLASSIFIED', AI) or r['match_confidence'] == 'override':
        continue
    subject = parse_title(name)[0]
    if _AI_TITLE.search(subject) and r['theme'] in SKILL_THEMES and not (
            CL.T[r['topic_id']]['ai_era_flag'] == 'New' and PEOPLE_WORDS.search(subject)):
        fails.append(f"{sl} | {name}: an AI programme filed under {r['theme']} / {r['topic']} ({r['match_why']})")

# 4. the review list
review = []
for (sl, name), r in tagged.items():
    if r['match_confidence'] in ('low', 'fallback', 'none'):
        review.append(dict(school_slug=sl, programme_name=name, theme=r['theme'], topic=r['topic'],
                           reason=f"filed on a broad keyword: {r['match_why']}"))
    elif r['match_confidence'] == 'override':
        rule = CL.classify(dict(r, programme_name=name, school_slug=sl, key_topics='', target_audience=''), use_overrides=False)
        if rule['topic_id'] and CL.theme(rule['topic_id']) != r['theme'] and rule['confidence'] in ('high', 'officer-rule'):
            review.append(dict(school_slug=sl, programme_name=name, theme=r['theme'], topic=r['topic'],
                               reason=f"hand override; the rules alone would say {CL.theme(rule['topic_id'])} / "
                                      f"{CL.T[rule['topic_id']]['topic']} ({rule['why']})"))
used = collections.Counter()
for sch, frag, _ in CL.overrides:
    used[(sch, frag)] = sum(1 for (sl, n) in tagged if sl == sch and frag in n.lower())
for k, n in used.items():
    if n == 0:
        notes.append(f"override matches no programme (renamed or gone?): {k[0]} | {k[1]}")
with open(R / 'outputs' / 'classification_review.csv', 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=['school_slug', 'programme_name', 'theme', 'topic', 'reason'], quoting=csv.QUOTE_ALL)
    w.writeheader(); w.writerows(sorted(review, key=lambda x: (x['reason'][:10], x['school_slug'])))

for n in notes:
    print('note:', n)
print(f"classification: {len(tagged)} programmes, {sum(1 for _ in open(R / 'data' / 'classification_checks.csv')) - 1} "
      f"hand-settled checks, {len(TITLES)} rule tests; {len(review)} to review in outputs/classification_review.csv")
if fails:
    print(f"\n{len(fails)} classification check(s) failed:")
    for f_ in fails:
        print('  FAIL', f_)
    sys.exit(1)
print('all classification checks pass')
