#!/usr/bin/env python3
"""Supply x demand analysis. Produces the matrices and the gap register."""
import csv, re, collections, json, os

import pathlib as _pl; BASE=str(_pl.Path(__file__).resolve().parent.parent)
tax=list(csv.DictReader(open(f'{BASE}/data/taxonomy.csv',encoding='utf-8')))
tmap={t['topic_id']:t for t in tax}
prog=list(csv.DictReader(open(f'{BASE}/programmes_tagged.csv',encoding='utf-8')))
dem=list(csv.DictReader(open(f'{BASE}/demand/demand_signals.csv',encoding='utf-8')))

INDIA={'isb','iima','iimb','iimc','iimk','iiml'}
GLOBAL={'hbs','wharton','insead','lbs','imd'}
COMP_INDIA=INDIA-{'isb'}
SCHOOLS=['isb']+sorted(COMP_INDIA)+sorted(GLOBAL)

# ---------- map demand signals to topics with the same keyword engine ----------
pats=[]
for t in tax:
    for kw in t['keywords'].split(';'):
        kw=kw.strip()
        if kw: pats.append((re.compile(kw,re.I),t))

# Manual mapping for demand signals whose vocabulary is a SKILLS taxonomy
# phrase with no catalogue equivalent. Keyed on a substring of the verbatim
# skill; value is a topic NAME (resolved below, fails loudly if renamed).
MANUAL_DEMAND={
 "Technological literacy":"Data and AI literacy for non-technical leaders",
 "Creative thinking":"Critical thinking and problem solving",
 "Analytical thinking":"Critical thinking and problem solving",
 "Curiosity and lifelong learning":"Learning, development and capability building",
 "Talent management":"Leadership development and succession architecture",
 "Skills disruption":"Workforce planning and skills-based organisation",
 "Upskilling as workforce strategy":"Workforce planning and skills-based organisation",
 "Reskilling to work alongside AI":"Building AI fluency and adoption in the workforce",
 "AI and information processing":"Generative AI foundations and prompting",
 "AI and big data":"Business analytics for decision-making",
 "Go-to-market strategy":"Sales operations, enablement and AI in sales",
 "Data & analytics":"Business analytics for decision-making",
 "Business & growth":"Growth strategy and scaling",
 "Stakeholder management; strategic business transformation":"Leading change and transformation",
 "Conflict mitigation":"Conflict management and mediation skills",
 "Process optimisation":"Operational excellence and process improvement",
 "Stakeholder management; budget":"Budgeting, forecasting and FP&A",
 "Leadership training":"Leadership development and succession architecture",
 "AI/ML roles":"AI and machine learning fundamentals for executives",
 "Keeping pace with technology":"AI strategy for the enterprise",
 "Organisational flattening":"Redesigning managerial work around AI",
 "Organisational/workforce adaptability":"Leading in uncertainty, volatility and ambiguity",
 "Workflow redesign":"Redesigning managerial work around AI",
 "Leadership":"Leadership styles and situational leadership",
 "Executive education market":"",
 "AI tools":"Generative AI foundations and prompting",
}
_byname={t['topic']:t['topic_id'] for t in tax}
_bad=[v for v in MANUAL_DEMAND.values() if v and v not in _byname]
assert not _bad, f"manual demand targets not in taxonomy: {_bad}"

dem_by_topic=collections.defaultdict(list)
dem_unmapped=[]
for d in dem:
    txt=(d['skill_or_topic_verbatim']+' '+d.get('note','')+' '+d.get('metric_verbatim',''))
    sc=collections.Counter()
    for pat,t in pats:
        if pat.search(d['skill_or_topic_verbatim']): sc[t['topic_id']]+=3
        elif pat.search(txt): sc[t['topic_id']]+=1
    man=None
    for frag,topicname in MANUAL_DEMAND.items():
        if frag.lower() in d['skill_or_topic_verbatim'].lower():
            man=_byname.get(topicname) if topicname else None
            break
    if man:
        dem_by_topic[man].append(d); d['_topic']=man; continue
    if sc:
        best=sc.most_common(1)[0][0]
        dem_by_topic[best].append(d)
        d['_topic']=best
    else:
        dem_unmapped.append(d); d['_topic']=''

# demand strength per topic: distinct sources x geographies, rising only
def demand_score(tid):
    ds=[d for d in dem_by_topic.get(tid,[]) if d['direction']=='rising']
    srcs={d['source'] for d in ds}; geos={d['geography'] for d in ds}
    sen={d['seniority_relevance'] for d in ds}
    # 2 pts per distinct source (cap 10), 1 per geography, +2 if senior-relevant
    return min(len(srcs),5)*2 + len(geos) + (2 if ('Senior' in sen or 'All' in sen) else 0), srcs, geos

# roll demand up to subtheme and theme (topics inherit their parents' evidence)
sub_dem=collections.defaultdict(set); theme_dem=collections.defaultdict(set)
for tid,ds in dem_by_topic.items():
    t=tmap[tid]
    for d in ds:
        if d['direction']=='rising':
            sub_dem[t['subtheme_id']].add(d['source']); theme_dem[t['theme']].add(d['source'])


# --- provenance flags: which topics are inflated by construction -------------
import importlib.util as _ilu
_cl=open(f'{BASE}/scripts/classify.py').read()
_names=set(re.findall(r'"([^"]+)"\)[,\s]*$',_cl,re.M))
SUPPLY_RESIDUAL={n for n in _names if n in {t['topic'] for t in tax}}
# fallback targets (supply-side residual buckets)
_fb=_cl[_cl.index('FALLBACK=['):_cl.index('_byname={')]
SUPPLY_RESIDUAL={n for n in re.findall(r'"([^"]{8,})"',_fb) if n in {t['topic'] for t in tax}}
DEMAND_MANUAL={v for v in MANUAL_DEMAND.values() if v}

# ---------- supply counts ----------
def counts(key):
    out=collections.defaultdict(lambda: collections.Counter())
    for p in prog:
        if p['theme']=='UNCLASSIFIED': continue
        out[p[key]][p['school_slug']]+=1
    return out

theme_c=counts('theme'); sub_c=counts('subtheme'); topic_c=counts('topic_id')
topic_c2=collections.defaultdict(lambda: collections.Counter())  # primary OR secondary
for p_ in prog:
    if p_['theme']=='UNCLASSIFIED': continue
    for tid in {p_['topic_id'],p_['secondary_topic_id']}-{''}:
        topic_c2[tid][p_['school_slug']]+=1

def w(path,rows,fields):
    with open(f'{BASE}/{path}','w',newline='',encoding='utf-8') as f:
        ww=csv.DictWriter(f,fieldnames=fields,quoting=csv.QUOTE_ALL); ww.writeheader(); ww.writerows(rows)

# ---- Matrix 1: theme x school ----
order=[t['theme'] for t in tax]
themes=list(dict.fromkeys(order))
m1=[]
for th in themes:
    c=theme_c[th]
    isb=c['isb']; ind=sum(c[s] for s in COMP_INDIA); glo=sum(c[s] for s in GLOBAL)
    tot_ind_prod=sum(1 for p in prog if p['school_slug'] in COMP_INDIA)
    tot_glo_prod=sum(1 for p in prog if p['school_slug'] in GLOBAL)
    isb_tot=sum(1 for p in prog if p['school_slug']=='isb')
    row=dict(theme=th, isb=isb,
        isb_share_pct=round(100*isb/isb_tot,1),
        india_comp=ind, india_comp_share_pct=round(100*ind/tot_ind_prod,1),
        global_comp=glo, global_share_pct=round(100*glo/tot_glo_prod,1),
        demand_sources=len(theme_dem[th]))
    for s in SCHOOLS: row[s]=c[s]
    m1.append(row)
w('outputs/matrix_theme_by_school.csv',m1,list(m1[0].keys()))

# ---- Matrix 2: subtheme x school ----
m2=[]
seen=set()
for t in tax:
    if t['subtheme_id'] in seen: continue
    seen.add(t['subtheme_id'])
    c=sub_c[t['subtheme']]
    # secondary-topic coverage rolled up to the sub-theme, so a product taught
    # here but SOLD as something else is visible instead of reading as a zero
    _sub_topics={x['topic_id'] for x in tax if x['subtheme_id']==t['subtheme_id']}
    _sec=collections.Counter()
    for _p in prog:
        if _p['secondary_topic_id'] in _sub_topics and _p['topic_id'] not in _sub_topics:
            _sec[_p['school_slug']]+=1
    row=dict(theme=t['theme'],subtheme=t['subtheme'],subtheme_id=t['subtheme_id'],
             isb=c['isb'],india_comp=sum(c[s] for s in COMP_INDIA),
             global_comp=sum(c[s] for s in GLOBAL),
             isb_also_covers=_sec['isb'],
             peers_also_cover=sum(_sec[s] for s in SCHOOLS if s!='isb'),
             demand_sources=len(sub_dem[t['subtheme_id']]))
    for s in SCHOOLS: row[s]=c[s]
    m2.append(row)
w('outputs/matrix_subtheme_by_school.csv',m2,list(m2[0].keys()))

# ---- Matrix 3: topic level with demand ----
m3=[]
for t in tax:
    c=topic_c[t['topic_id']]
    dscore,srcs,geos=demand_score(t['topic_id'])
    isb=c['isb']; ind=sum(c[s] for s in COMP_INDIA); glo=sum(c[s] for s in GLOBAL)
    schools_present=sum(1 for s in SCHOOLS if c[s]>0)
    row=dict(theme=t['theme'],subtheme=t['subtheme'],topic=t['topic'],topic_id=t['topic_id'],
      ai_era_flag=t['ai_era_flag'],isb=isb,india_comp=ind,global_comp=glo,
      total_supply=isb+ind+glo,schools_present=schools_present,
      isb_incl_secondary=topic_c2[t['topic_id']]['isb'],
      supply_incl_secondary=sum(topic_c2[t['topic_id']][s] for s in SCHOOLS),
      supply_is_residual_bucket='Y' if t['topic'] in SUPPLY_RESIDUAL else '',
      demand_is_manually_mapped='Y' if t['topic_id'] in DEMAND_MANUAL else '',
      demand_score=dscore,demand_sources=len(srcs),demand_geographies=";".join(sorted(geos)),
      demand_source_list=" | ".join(sorted(srcs))[:300])
    m3.append(row)
w('outputs/matrix_topic_full.csv',m3,list(m3[0].keys()))

# ---- Gap register ----
gaps=[]
for r in m3:
    isb,ind,glo,d=r['isb'],r['india_comp'],r['global_comp'],r['demand_score']
    comp=ind+glo
    # a topic competitors cover only as a module still counts as covered
    comp_broad=r['supply_incl_secondary']-r['isb_incl_secondary']
    comp=max(comp,comp_broad)
    # ISB presence = PRIMARY topic only: a product is what it is sold as.
    # Competitor coverage = broad: a topic taught as a module is not whitespace.
    if isb==0 and comp>=6 and d>=6: kind='FOLLOW - proven market, ISB absent'
    elif isb==0 and comp>=6 and d<6: kind='FOLLOW (weak demand evidence) - competitors crowded'
    elif isb==0 and comp<=2 and d>=8: kind='LEAD - demand evidenced, supply thin everywhere'
    elif isb==0 and 3<=comp<=5 and d>=8: kind='LEAD/FAST-FOLLOW - early market'
    elif isb>0 and comp>=10 and d>=8: kind='DEFEND & DEEPEN - ISB present in a hot crowded space'
    elif isb>0 and d<4 and comp<=3: kind='REVIEW - ISB present, little demand or peer evidence'
    elif isb==0 and comp==0 and d>=8: kind='LEAD (greenfield) - nobody supplies it'
    else: kind=''
    if kind:
        gaps.append(dict(call=kind,**r))
prio={'LEAD (greenfield) - nobody supplies it':0,'LEAD - demand evidenced, supply thin everywhere':1,
  'LEAD/FAST-FOLLOW - early market':2,'FOLLOW - proven market, ISB absent':3,
  'DEFEND & DEEPEN - ISB present in a hot crowded space':4,
  'FOLLOW (weak demand evidence) - competitors crowded':5,'REVIEW - ISB present, little demand or peer evidence':6}
gaps.sort(key=lambda g:(prio[g['call']],-g['demand_score'],-g['total_supply']))
w('outputs/gap_register.csv',gaps,list(gaps[0].keys()))

# ---- front-loading: what schools flagged new ----
newc=collections.defaultdict(lambda: collections.Counter())
for p in prog:
    if (p['is_new'] or '').strip().upper().startswith('Y'):
        newc[p['theme']][p['school_slug']]+=1
m4=[dict(theme=th,total_new=sum(newc[th].values()),
         **{s:newc[th][s] for s in SCHOOLS}) for th in themes if sum(newc[th].values())>0]
m4.sort(key=lambda r:-r['total_new'])
if m4: w('outputs/front_loading_new_products.csv',m4,list(m4[0].keys()))

# ---- AI-era coverage ----
ai=collections.defaultdict(lambda: collections.Counter())
for p in prog:
    if p['ai_era_flag'] in ('New','Transformed'):
        ai[p['ai_era_flag']][p['school_slug']]+=1
m5=[]
for s in SCHOOLS:
    tot=sum(1 for p in prog if p['school_slug']==s)
    m5.append(dict(school=s,products=tot,ai_new=ai['New'][s],ai_transformed=ai['Transformed'][s],
      ai_era_total=ai['New'][s]+ai['Transformed'][s],
      ai_era_pct=round(100*(ai['New'][s]+ai['Transformed'][s])/tot,1) if tot else 0))
m5.sort(key=lambda r:-r['ai_era_pct'])
w('outputs/ai_era_exposure_by_school.csv',m5,list(m5[0].keys()))

# ---- unmapped demand (must be reported, not hidden) ----
if dem_unmapped:
    w('outputs/demand_unmapped.csv',[{k:v for k,v in d.items() if not k.startswith('_')} for d in dem_unmapped],
      [k for k in dem_unmapped[0].keys() if not k.startswith('_')])

print("=== PORTFOLIO SIZE (distinct products) ===")
for s in SCHOOLS: print(f"  {s:9s} {sum(1 for p in prog if p['school_slug']==s):4d}")
print("\n=== AI-ERA EXPOSURE ===")
for r in m5: print(f"  {r['school']:9s} {r['ai_era_pct']:5.1f}%  ({r['ai_era_total']}/{r['products']})")
print("\n=== THEME: ISB share vs global peers' share ===")
for r in sorted(m1,key=lambda x:-x['global_share_pct']):
    print(f"  {r['theme'][:42]:42s} ISB {r['isb']:2d} ({r['isb_share_pct']:4.1f}%) | IndiaComp {r['india_comp']:3d} ({r['india_comp_share_pct']:4.1f}%) | Global {r['global_comp']:3d} ({r['global_share_pct']:4.1f}%) | demand src {r['demand_sources']}")
print("\n=== GAP REGISTER: counts by call ===")
for k,v in collections.Counter(g['call'] for g in gaps).most_common(): print(f"  {v:3d}  {k}")
print(f"\ndemand signals mapped: {len(dem)-len(dem_unmapped)}/{len(dem)}; unmapped {len(dem_unmapped)}")
