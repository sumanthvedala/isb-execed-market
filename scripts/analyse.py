#!/usr/bin/env python3
"""Supply x demand analysis. Produces the matrices and the gap register."""
import csv, re, collections, json, os

import pathlib as _pl; BASE=str(_pl.Path(__file__).resolve().parent.parent)
tax=list(csv.DictReader(open(f'{BASE}/data/taxonomy.csv',encoding='utf-8')))
tmap={t['topic_id']:t for t in tax}
prog=list(csv.DictReader(open(f'{BASE}/programmes_tagged.csv',encoding='utf-8')))
dem=list(csv.DictReader(open(f'{BASE}/demand/demand_signals.csv',encoding='utf-8')))

# school groups come from data/schools.csv, so adding a school is one row there
_sch=list(csv.DictReader(open(f'{BASE}/data/schools.csv',encoding='utf-8')))
COMP_INDIA={s['slug'] for s in _sch if s['group']=='India'}
GLOBAL={s['slug'] for s in _sch if s['group']=='Global'}
PLATFORM={s['slug'] for s in _sch if s['group']=='Platform'}
SCHOOLS=[s['slug'] for s in _sch]
PEERS=[s for s in SCHOOLS if s!='isb']

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
    plat=sum(c[s] for s in PLATFORM)
    tot=lambda grp:sum(1 for p in prog if p['school_slug'] in grp) or 1
    row=dict(theme=th, isb=isb,
        isb_share_pct=round(100*isb/tot({'isb'}),1),
        india_comp=ind, india_comp_share_pct=round(100*ind/tot(COMP_INDIA),1),
        global_comp=glo, global_share_pct=round(100*glo/tot(GLOBAL),1),
        platform_comp=plat, platform_share_pct=round(100*plat/tot(PLATFORM),1),
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
             platform_comp=sum(c[s] for s in PLATFORM),
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
    plat=sum(c[s] for s in PLATFORM)
    schools_present=sum(1 for s in SCHOOLS if c[s]>0)
    c2=topic_c2[t['topic_id']]
    row=dict(theme=t['theme'],subtheme=t['subtheme'],topic=t['topic'],topic_id=t['topic_id'],
      ai_era_flag=t['ai_era_flag'],isb=isb,india_comp=ind,global_comp=glo,platform_comp=plat,
      total_supply=isb+ind+glo+plat,schools_present=schools_present,
      peers_present=sum(1 for s in PEERS if c2[s]>0),
      peers_new=sum(1 for p_ in prog if p_['school_slug']!='isb' and p_['topic_id']==t['topic_id']
                    and (p_['is_new'] or '').upper().startswith('Y')),
      isb_incl_secondary=topic_c2[t['topic_id']]['isb'],
      supply_incl_secondary=sum(topic_c2[t['topic_id']][s] for s in SCHOOLS),
      supply_is_residual_bucket='Y' if t['topic'] in SUPPLY_RESIDUAL else '',
      demand_is_manually_mapped='Y' if t['topic_id'] in DEMAND_MANUAL else '',
      demand_score=dscore,demand_sources=len(srcs),demand_geographies=";".join(sorted(geos)),
      demand_source_list=" | ".join(sorted(srcs))[:300])
    m3.append(row)
w('outputs/matrix_topic_full.csv',m3,list(m3[0].keys()))

# ---- Gap register ----
# Peer pressure is counted in SCHOOLS, not products. With 19 peers, including
# platforms that list dozens of near-identical certificates, a product count
# rewards catalogue size; the number of distinct peers that chose to sell a
# topic (as a product or a module) is the better read of a proven market.
# ISB presence = PRIMARY topic only: a product is what it is sold as.
isb_subs={p['subtheme'] for p in prog if p['school_slug']=='isb' and p['theme']!='UNCLASSIFIED'}
CROWDED,EARLY=5,2      # peers present: >=5 crowded, 2-4 early market, <=1 thin
DEM_HI,DEM_MID,DEM_LO=8,6,4
gaps=[]
for r in m3:
    isb,d,peers=r['isb'],r['demand_score'],r['peers_present']
    adj=r['subtheme'] in isb_subs
    if isb==0 and peers<EARLY and d>=DEM_HI: call,why='LEAD','demand evidenced, almost nobody sells it'
    elif isb==0 and peers<CROWDED and d>=DEM_HI: call,why='LEAD','demand evidenced, early market'
    elif isb==0 and peers>=CROWDED and d>=DEM_MID and adj: call,why='DIVERSIFY','proven market next to a sub-theme ISB already sells in'
    elif isb==0 and peers>=CROWDED and d>=DEM_MID: call,why='FOLLOW','proven market, ISB absent'
    elif isb==0 and peers>=CROWDED: call,why='WATCH','peers crowd in, demand evidence thin'
    elif isb>0 and peers>=CROWDED+1 and d>=DEM_HI: call,why='DEFEND','ISB present in a hot, crowded space'
    elif isb>0 and d>=DEM_HI: call,why='DEEPEN','ISB present, demand strong, few peers: room to own it'
    elif isb>0 and d<DEM_LO and peers<=EARLY: call,why='REVIEW','ISB present, little demand or peer evidence'
    else: call=why=''
    if call:
        gaps.append(dict(call=call,why=why,**r))
prio={'LEAD':0,'DIVERSIFY':1,'FOLLOW':2,'DEFEND':3,'DEEPEN':4,'WATCH':5,'REVIEW':6}
gaps.sort(key=lambda g:(prio[g['call']],-g['demand_score'],-g['peers_present']))
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
