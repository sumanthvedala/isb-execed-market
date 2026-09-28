#!/usr/bin/env python3
"""Normalises 259 demand signals into a 0-100 Demand Index per topic, and carries
a SEPARATE 2027-31 Outlook that is Claude's judgment, not evidence.

The two are deliberately not blended into one number. The Index says what the
world has already published. The Outlook says where it goes next. Mixing them
would let judgment borrow the authority of the evidence.
"""
import csv, collections

import pathlib as _pl; BASE = str(_pl.Path(__file__).resolve().parent.parent)
tax = list(csv.DictReader(open(f'{BASE}/data/taxonomy.csv', encoding='utf-8')))
tid2 = {t['topic_id']: t for t in tax}
byname = {t['topic']: t['topic_id'] for t in tax}
sig = list(csv.DictReader(open(f'{BASE}/data/demand_all.csv', encoding='utf-8')))

# ---------------------------------------------------------------- Demand Index
# Weights chosen so that a dated legal obligation beats a survey of intentions,
# and breadth of independent sources beats any single loud one.
SIGNAL_WEIGHT = {
    'policy/regulation': 28,   # non-discretionary, dated
    'job postings':      24,   # behaviour, not intent
    'industry body':     18,
    'consultancy research': 16,
    'employer survey':   14,   # stated intent
    'learner platform':  12,
    'news':               8,
    'expert/HBR':         8,   # informs the buyer, does not measure demand
}
SENIORITY_WEIGHT = {'Senior': 15, 'All': 11, 'Mid': 8, 'Entry': 2, 'Unknown': 4}

agg = collections.defaultdict(lambda: {
    'srcs': set(), 'geo': set(), 'stypes': set(), 'sen': set(),
    'horizon_fwd': False, 'rising': 0, 'declining': 0, 'rows': []})

for r in sig:
    t = r['topic_id']
    if not t or t not in tid2:
        continue
    a = agg[t]
    a['rows'].append(r)
    if r['direction'] == 'declining':
        a['declining'] += 1
        continue
    a['rising'] += 1
    a['srcs'].add(r['source'].strip())
    a['geo'].add(r['geo'].strip())
    a['stypes'].add(r['stype'].strip())
    a['sen'].add(r['seniority'].strip())
    if r['horizon'] in ('2027-2029', '2030+'):
        a['horizon_fwd'] = True

def index_for(a):
    if not a['srcs']:
        return 0, {}
    breadth = min(len(a['srcs']), 6) / 6 * 30
    geo     = min(len(a['geo']), 4) / 4 * 12
    quality = max((SIGNAL_WEIGHT.get(s, 6) for s in a['stypes']), default=6)
    horizon = 15 if a['horizon_fwd'] else 8
    sen     = max((SENIORITY_WEIGHT.get(s, 4) for s in a['sen']), default=4)
    total = breadth + geo + quality + horizon + sen
    return round(total), dict(breadth=round(breadth), geography=round(geo),
                              signal_quality=quality, horizon=horizon, seniority=sen)

# ------------------------------------------------------- Outlook 2027-31 (mine)
# 5 structurally locked in · 4 grows · 3 holds · 2 softens · 1 declines
# Every line is Claude's judgment. Where evidence points the other way, the
# rationale says so rather than hiding it.
O = {
 # --- locked in by a dated obligation or an irreversible structural shift
 "Building AI fluency and adoption in the workforce": (5, "EU AI Act Art.4 in force, RBI FREE-AI asks for board and C-suite AI literacy, and PwC-FICCI puts GCC leadership literacy at 27%. Obligation plus measured gap."),
 "AI governance frameworks and operating models": (5, "Annex III high-risk duties bite Dec 2027, inside the window; 1,997 US postings already 73% senior-or-above. The buyer exists today."),
 "Board and ExCo AI literacy as regulatory evidence": (5, "A programme a company can point at to evidence Art.4, DORA and FREE-AI compliance. Non-discretionary and nobody sells it."),
 "AI regulation and compliance (EU AI Act, DPDP, sectoral)": (5, "Three dated regimes converge in-window: AI Act Dec 2027, DPDP 13 May 2027, RBI AI policy."),
 "Data privacy and protection": (5, "DPDP substantive obligations and penalties to Rs 250 cr commence 13 May 2027."),
 "IT services, GCC and global capability centre leadership": (5, "Global roles held from India 115 (2015) to 6,500 (2024) to a projected 30,000 by 2030. No Indian school sells this at scale."),
 "Influencing global headquarters from a captive centre": (5, "Named by GCC leaders as the top capability gap and taught by nobody. Same driver as GCC growth."),
 # --- grows
 "Leading teams that include AI agents": (4, "BCG: 65% of managers expect agents to take half their role within three years. Early market, real mechanism."),
 "Redesigning managerial work around AI": (4, "McKinsey and Deloitte both name change-absorption, not AI skill, as the binding constraint."),
 "Supervising and quality-assuring AI output": (4, "HBR finds middle managers absorbing AI validation and error correction under unchanged delivery pressure."),
 "Work redesign to convert AI time savings into output": (4, "BCG: 47% of workers now spend more time directing AI than working, and India is weakest at converting that time."),
 "Human-agent ratio and span-of-control design": (4, "Span of control roughly doubled pre-AI (Gusto). Agents make it an explicit design question."),
 "AI-augmented decision-making and judgment": (4, "Deloitte: 60% of executives use AI in decisions, 5% say they manage it well. Gap is wide and named."),
 "Board oversight of AI": (4, "RBI mandates a board-approved AI policy with annual review; AI Act makes boards accountable."),
 "Trust, accountability and human oversight of AI decisions": (4, "AI Act Art.14 makes human oversight a competence requirement, not a checkbox."),
 "Model observability and assurance for leaders": (4, "41% of AI-governance postings ask for it. No programme anywhere addresses it for a leadership audience."),
 "India regulatory stack for boards: DPDP, BRSR and RBI AI": (4, "Three Indian obligations land together; no school bundles them for a board audience."),
 "Leadership styles and situational leadership": (4, "WEF: leadership and social influence rose 22pp in employer-stated importance between 2023 and 2025, ahead of AI and big data at 17pp."),
 "Leading change and transformation": (4, "The constraint every consultancy independently names. Rises as AI raises the change load."),
 "Workforce planning and skills-based organisation": (4, "Lightcast: a third of the average job's skills changed 2021-24, top quartile 75%. Churn roughly doubled per unit time."),
 "AI in HR: hiring, development and productivity": (4, "HR leads AI-skill posting growth at 66%, and AI in hiring and promotion is Annex III high-risk. Obligation plus adoption."),
 "Cybersecurity strategy for leaders and boards": (4, "DORA board continuing-education duty plus RBI operational-resilience training mandates."),
 "Hospital and healthcare operations management": (4, "India produces ~2,500 hospital-management professionals a year against 21,000 needed now and ~45,000 by 2030."),
 "Healthcare strategy, payers and providers": (4, "Same supply gap, and ISB already has the Max Institute and Sarang Deo."),
 "Personal resilience, wellbeing and burnout": (4, "47% of midlevel managers report AI strain against 31% of executives. The load is measured, not asserted."),
 "Emotional intelligence and self-awareness": (4, "Rides the same WEF social-influence delta. Rises as more routine analysis is automated."),
 "Leading in uncertainty, volatility and ambiguity": (4, "Deloitte: 85% say adaptability is critical, 7% are delivering it."),
 "Supply chain resilience and risk": (4, "Tariffs, friendshoring and export controls are live and not reverting inside the window."),
 "Geopolitics for business leaders and boards": (4, "UNICON names it the underserved topic; IMD and MIT Sloan have both launched. Demand is real, supply is thin in India."),
 "Learning, development and capability building": (4, "WEF CPO Outlook now ranks job and org redesign (74%) above upskilling (70%); both land on this buyer."),
 "Board effectiveness and director duties": (4, "Independent-director obligations plus AI and ESG accountability landing on boards at once."),
 "General management programmes for senior leaders": (4, "India-specific: KPMG/AIMA Management Capability Development Index fell from 76 (2011) to 69.7 (2024). Classic GM is not saturated here even as Western manager seats contract."),
 "Leading mid-level to senior transition": (4, "PwC India: contraction is at junior level, 30% say mid-level stable, 19% expect senior increases. India does not import the Western squeeze."),
 # --- holds
 "Generative AI foundations and prompting": (3, "Highest evidence count in the whole dataset, and the fastest to commoditise. Demand is real now and will be met cheaply by 2029."),
 "AI and machine learning fundamentals for executives": (3, "Same commoditisation path. Coverage play, not a margin play."),
 "Data and AI literacy for non-technical leaders": (3, "Real, but converging with the free tier."),
 "Business analytics for decision-making": (3, "Mature, crowded, still bought."),
 "AI strategy for the enterprise": (3, "PwC: 56% of 4,454 CEOs report no significant financial benefit from AI yet. Strategy demand holds but the narrative is cooling."),
 "Evaluating AI use cases and ROI": (3, "Follows the same cooling as AI strategy; sharper and more defensible than it."),
 "Competitive strategy and advantage": (3, "Perennial. Neither AI nor regulation moves it much."),
 "Strategy execution and implementation": (3, "Perennial, under-taught, unchanged."),
 "Negotiation for commercial outcomes": (3, "The argument that AI makes human skills scarcer is asserted, not measured. Do not sell it as evidenced."),
 "Business storytelling and narrative": (3, "Same caveat. Stable demand, no new driver."),
 "Executive presence and personal brand": (3, "Stable; ISB's best seller sits here, which is a revenue fact, not a demand trend."),
 "Critical thinking and problem solving": (3, "WEF keeps it top-five, but it is hard to sell as a standalone product."),
 "Corporate finance and capital allocation": (3, "Perennial. Under-evidenced by skills-led sources, not under-demanded."),
 "Finance for non-finance managers": (3, "Perennial and heavily supplied."),
 "M&A strategy and deal rationale": (3, "Cyclical rather than structural."),
 "Project management": (3, "Mature, commoditised, certification-led."),
 "Operational excellence and process improvement": (3, "Mature. AI changes the tooling, not the demand level."),
 "Marketing strategy for executives": (3, "Stable; the AI disruption hits execution, not strategy."),
 "Sustainability and ESG strategy for the enterprise": (3, "Down in Europe, up in India. The CSRD omnibus cut ~42,000 companies from scope; SEBI BRSR value-chain rules push the other way."),
 "ESG reporting, assurance and CSRD/BRSR compliance": (3, "India rising, Europe falling sharply. Net flat, and the two must not be averaged in a pitch."),
 "Women's leadership and gender in the workplace": (3, "Steady institutional demand, no new driver in the window."),
 "CHRO and HR leadership": (3, "Holds; the growth is in the AI-in-HR topic, not the generic CHRO agenda."),
 "Talent acquisition and employer brand": (3, "High evidence score, but it is practitioner-certification territory (SHRM, CIPD), not business-school territory."),
 # --- added so every evidenced topic carries a judgment
 "Leading through AI-driven workforce disruption": (4, "Strong survey backing but the Fed (7.3m firm-months) finds no evidence AI-adopting industries post fewer jobs. Real as a leadership anxiety, weaker as a labour fact."),
 "AI risk, safety and model assurance": (4, "Rides the Annex III timeline with AI governance; narrower audience, so a module rather than a product."),
 "Agentic AI and autonomous workflows": (4, "Fastest-moving concept in the set. High demand, high obsolescence risk in content."),
 "Technology and operational resilience risk": (4, "DORA and RBI operational-resilience training mandates both bite in-window."),
 "Board oversight of strategy, technology and AI": (4, "Same board accountability wave; pairs naturally with a board credential."),
 "Defence, security and strategic affairs": (3, "India indigenisation is real but the buyer is government and PSU, not open-enrolment."),
 "Business model innovation and reinvention": (4, "PwC: 56% of CEOs see no AI financial benefit yet, which is a business-model problem, not a technology one."),
 "Manufacturing strategy and Industry 4.0 operations": (3, "PLI-driven and real, but ISB's manufacturing assets sit in Munjal, outside Exec Ed."),
 "Organisation design and operating models": (4, "WEF CPO Outlook now ranks job and org redesign (74%) above upskilling (70%). The most under-supplied classic topic."),
 "Leading in the first 90 days / role transition": (3, "IMD and IIM-C both prove the premium; steady rather than growing."),
 "Sales leadership and sales force management": (3, "Stable; the change is in sales ops and AI tooling, not leadership."),
 "Starting and scaling a venture": (3, "Perennial; ISB's asset here is an incubator brand, not a research centre."),
 "Decision-making, biases and behavioural judgment": (4, "Gains value as AI drafts more of the analysis, though the mechanism is argued rather than measured."),
 "CEO / top management leadership": (3, "Perennial and the most crowded tier in the market."),
 "Digital health, health analytics and AI in medicine": (4, "ABDM plus India's hospital-management shortage; ISB has the Max Institute."),
 "Leading high-performing teams": (3, "Perennial, heavily supplied."),
 "Growth strategy and scaling": (3, "Perennial."),
 "AI for the CFO and finance function": (4, "Finance is third in AI-skill posting growth at 40% and the CFO seat is where AI ROI gets adjudicated."),
 "Generative AI for marketing and creative": (3, "High adoption, low willingness to pay at executive level; it is a practitioner product."),
 "Sales operations, enablement and AI in sales": (4, "Almost no supply anywhere and a clear commercial payback story."),
 "Compliance, ethics and integrity programmes": (4, "Carried by the same regulatory wave; the audience is the GC and CCO more than the CEO."),
 "Leadership development and succession architecture": (3, "Steady institutional demand; rarely bought as an open programme."),
 # --- softens
 "Net-zero transition and decarbonisation": (2, "CS3D Article 22 climate-transition-plan duty deleted; CEEW puts India's green jobs in deployment and O&M, with no managerial layer."),
 "Digital marketing and performance media": (2, "The function most directly automated by the tools being sold into it."),
 "Sustainable finance, green bonds and climate risk in finance": (2, "Follows the European retreat; India's version is too small to carry a programme yet."),
}
missing = [k for k in O if k not in byname]
assert not missing, f"outlook names not in taxonomy: {missing}"

out = []
for t in tax:
    a = agg.get(t['topic_id'], {'srcs': set(), 'geo': set(), 'stypes': set(), 'sen': set(),
                                'horizon_fwd': False, 'rising': 0, 'declining': 0, 'rows': []})
    idx, parts = index_for(a)
    sc, why = O.get(t['topic'], ('', ''))
    out.append(dict(
        theme=t['theme'], subtheme=t['subtheme'], topic=t['topic'], topic_id=t['topic_id'],
        ai_era_flag=t['ai_era_flag'],
        demand_index=idx,
        sources=len(a['srcs']), geographies=len(a['geo']),
        best_signal=max(a['stypes'], key=lambda s: SIGNAL_WEIGHT.get(s, 6)) if a['stypes'] else '',
        forward_dated='Y' if a['horizon_fwd'] else '',
        contested='Y' if a['declining'] else '',
        outlook_2027_31=sc, outlook_rationale=why,
        component_breadth=parts.get('breadth', 0), component_geography=parts.get('geography', 0),
        component_signal=parts.get('signal_quality', 0), component_horizon=parts.get('horizon', 0),
        component_seniority=parts.get('seniority', 0),
        source_list=' | '.join(sorted(a['srcs']))[:400]))

with open(f'{BASE}/outputs/demand_index.csv', 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=list(out[0].keys()), quoting=csv.QUOTE_ALL)
    w.writeheader(); w.writerows(out)

scored = [o for o in out if o['demand_index'] > 0]
print(f"topics: {len(out)} | with evidence: {len(scored)} | hand-assessed outlook: {len(O)}")
print(f"index range: {min(o['demand_index'] for o in scored)}-{max(o['demand_index'] for o in scored)}")
print("\nTOP 25 BY DEMAND INDEX")
print(f"{'idx':>4} {'out':>4}  {'src':>3} {'geo':>3}  {'best signal':18s} topic")
for o in sorted(scored, key=lambda x: -x['demand_index'])[:25]:
    print(f"{o['demand_index']:>4} {str(o['outlook_2027_31'] or '-'):>4}  {o['sources']:>3} {o['geographies']:>3}  "
          f"{o['best_signal'][:18]:18s} {o['topic'][:52]}")
