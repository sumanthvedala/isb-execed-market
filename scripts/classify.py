#!/usr/bin/env python3
"""Tags every captured programme to a taxonomy topic, deterministically.

Rebuildable: re-run after any catalogue refresh. Writes programmes_tagged.csv
(one row per distinct product per school) and coverage matrices.
"""
import csv, os, re, glob, collections, json

import pathlib as _pl; BASE=str(_pl.Path(__file__).resolve().parent.parent)
tax=list(csv.DictReader(open(f'{BASE}/data/taxonomy.csv',encoding='utf-8')))
# compile keyword patterns
pats=[]
for t in tax:
    for kw in t['keywords'].split(';'):
        kw=kw.strip()
        if kw: pats.append((re.compile(kw,re.I), t))

WEIGHT={'programme_name':3.0,'key_topics':1.0,'school_category':0.6,'target_audience':0.3}


# --- PRIORITY 1: named overrides -------------------------------------------
# Products where the keyword engine demonstrably misreads the title. Keyed on
# (school_slug, lowercase substring of the programme name) -> topic NAME.
OVERRIDES=[]
try:
    for _r in csv.DictReader(open(f'{BASE}/data/overrides.csv',encoding='utf-8')):
        OVERRIDES.append((_r['school_slug'].strip(),_r['name_contains'].strip().lower(),_r['topic'].strip()))
except FileNotFoundError:
    pass

# --- PRIORITY 2: chief-officer rule ----------------------------------------
# A CHRO programme teaches HR; a CFO programme teaches finance. Before this fix
# all 45 of them collapsed into the C-suite ladder topic, which zeroed ISB on
# HR strategy and on finance for executives. Primary = the function taught,
# secondary = the C-suite ladder, so the ladder is still countable.
LADDER="Becoming a C-suite officer (role-specific ladders)"
OFFICER=[
 (r'\bchro\b|chief human resource|human resources officer',"CHRO and HR leadership"),
 (r'\bcfo\b|chief financial officer',"Corporate finance and capital allocation"),
 (r'chief ai officer|\bcaio\b|chief product & ai|chief \w+ and ai officer|'
  r'chief technology and ai|\bctaio\b',"AI strategy for the enterprise"),
 (r'\bcdaio\b|chief digital',"Enterprise digital transformation strategy and roadmaps"),
 (r'\bcto\b|chief technology officer',"Enterprise digital transformation strategy and roadmaps"),
 (r'\bcmo\b|chief marketing|chief growth and marketing',"Marketing strategy for executives"),
 (r'\bcso\b|chief strategy officer',"Corporate strategy, portfolio and diversification"),
 (r'\bcoo\b|chief operating|chief operations',"Operational excellence and process improvement"),
 (r'\bcro\b|chief revenue officer',"Sales leadership and sales force management"),
 (r'chief product officer|\bcpo\b',"Product management and product marketing"),
 (r'chief legal officer',"Compliance, ethics and integrity programmes"),
 (r'\bceo\b|chief executive officer|owner/president|president/ceo',"CEO / top management leadership"),
]
OFFICER=[(re.compile(r,re.I),t) for r,t in OFFICER]

# --- PRIORITY 3: sector rule -----------------------------------------------
# "Advanced Management Programme for Healthcare" is a healthcare product, not a
# general-management one; the sector qualifier wins over the wrapper phrase.
SECTOR=[
 (r'for healthcare|in healthcare|healthcare management',"Healthcare strategy, payers and providers"),
 (r'for infrastructure|infrastructure management',
   "Infrastructure, construction and real estate development"),
 (r'for manufacturing|manufacturing management',"Manufacturing strategy and Industry 4.0 operations"),
 (r'for banking|banking management|\bbfsi\b',
   "Banking, financial services and insurance sector management"),
]
SECTOR=[(re.compile(r,re.I),t) for r,t in SECTOR]

# Out of scope: faculty development / academic-audience programmes are not
# executive education products sold to managers.
EXCLUDE=re.compile(r'faculty development|case teaching|case writing|case pedagog|'
  r'doctoral|participant-centered learning|participant centred learning|'
  r'research and academic publishing|teaching effectiveness|for teachers|'
  r'management development programme for faculty|'
  # degree programmes are out of scope (CATALOGUE_SPEC)
  r'\bmaster of\b|\bmasters? in\b|\be?mba\b|\bpgpx\b',re.I)

# Out of scope: MOOC marketplaces. Coursera and edX courses are not competing
# executive education products (decision, 30 Sep 2026).
MOOC=re.compile(r'coursera|\bedx\b|edx\.org|^iimbx',re.I)

# Fallback: broad single-concept terms, applied ONLY when nothing else matched.
# Weight is low by construction (scored separately) so a real match always wins.
FALLBACK=[
 (r'emerging c[fomt]o|owner/president|president/ceo|senior management program|'
  r'\bcmo\b|chief marketing|chief \w+ officer',"Becoming a C-suite officer (role-specific ladders)"),
 (r'\bboard\b|gobierno corporativo|sala de juntas|non.executive|\bdirector',
  "Board effectiveness and director duties"),
 (r'general management|management development program|management acceleration|'
  r'certificate in management|management foundations|program for executive development|'
  r'global executive program|executive programme in advanced general',
  "General management programmes for senior leaders"),
 (r'new product|product development',"Product management and product marketing"),
 (r'high performance organisation|high.performance organization',
  "Organisational culture and culture change"),
 (r'\bit management|information technology management',
  "Enterprise digital transformation strategy and roadmaps"),
 (r'public system|public sector management',"Public policy design and analysis"),
 (r'etiquette|personality development|grooming',"Executive presence and personal brand"),
 (r'neuroscience|brain',"Decision-making, biases and behavioural judgment"),
 (r'corporate failure|learning from failure',"Turnaround and restructuring leadership"),
 (r'behavio(u?)ral econom|behavioural science|nudge',"Organisational behaviour and motivation"),
 (r'extreme environment|adventure|expedition|military lead',
  "Leading in uncertainty, volatility and ambiguity"),
 (r'data to decision|analytics',"Business analytics for decision-making"),
 (r'master ?class.*financ|finance master',"Finance for non-finance managers"),
 (r'health ?care|health delivery|hospital',"Hospital and healthcare operations management"),
 (r'\binnovat',"Innovation strategy and portfolio"),
 (r'\bculture\b',"Organisational culture and culture change"),
 (r'\bsales\b',"Sales leadership and sales force management"),
 (r'\bmarketing\b',"Marketing strategy for executives"),
 (r'\bstrateg',"Competitive strategy and advantage"),
 (r'\bfinanc|account',"Finance for non-finance managers"),
 (r'\bhuman resource|\bhr\b|people manage|talent',"Strategic HR and business partnering"),
 (r'\boperations|supply|procure|logistic',"Operational excellence and process improvement"),
 (r'governance|complian|\blaw\b|legal|\brisk\b',"Enterprise risk management"),
 (r'sustainab|climate|esg|green',"Sustainability and ESG strategy for the enterprise"),
 (r'polic(y|ies)|government',"Public policy design and analysis"),
 (r'entrepreneur|startup|start-up|venture|family business|family enterprise',
  "Starting and scaling a venture"),
 (r'\bdigital|\btech|\bai\b|artificial intelligence',
  "Enterprise digital transformation strategy and roadmaps"),
 (r'stakeholder',"Media, investor and stakeholder communication"),
 (r'communicat|present|speak|storytell|writing|negotiat|influenc|persuas|'
  r'presence|coach|conflict|decision|thinking|productiv|career|emotional',
  "Public speaking, presentation and boardroom communication"),
 (r'\bleader|leading\b',"Leadership styles and situational leadership"),
 (r'\bmanagement programme|managing\b',"General management programmes for senior leaders"),
]
# resolve topic NAMES to ids, so a renamed/renumbered taxonomy fails loudly
_byname={t['topic']:t['topic_id'] for t in tax}
_missing=[n for _,n in FALLBACK if n not in _byname]
assert not _missing, f"fallback targets not in taxonomy: {_missing}"
FALLBACK=[(p,_byname[n]) for p,n in FALLBACK]
FALLBACK=[(re.compile(p,re.I),t) for p,t in FALLBACK]


_byname_all={t['topic']:t['topic_id'] for t in tax}
for _lst,_lbl in ((OVERRIDES,'OVERRIDES'),):
    _bad=[n for _,_,n in _lst if n not in _byname_all]
    assert not _bad, f"{_lbl} targets not in taxonomy: {_bad}"
_bad=[n for _,n in OFFICER if n not in _byname_all]+[n for _,n in SECTOR if n not in _byname_all]
assert not _bad, f"officer/sector targets not in taxonomy: {_bad}"
assert LADDER in _byname_all

def priority_topic(r):
    """Returns (primary_topic_id, secondary_topic_id, confidence) or None."""
    nm=(r.get('programme_name') or '')
    sl=r.get('school_slug','')
    low=nm.lower()
    for sch,frag,topic in OVERRIDES:
        if sch==sl and frag in low:
            # an override fixes the PRIMARY topic; the C-suite ladder is still
            # real coverage, so keep it as secondary where the title is an
            # officer programme, exactly as the officer rule does for peers.
            sec=''
            for pat,_t in OFFICER:
                if pat.search(nm):
                    sec=_byname_all[LADDER]
                    if re.search(r'\bai\b|artificial intelligence|\bcaio\b|\bctaio\b|\bcdaio\b|digital',nm,re.I):
                        sec=_byname_all["AI governance frameworks and operating models"]
                    break
            return _byname_all[topic],sec,'override'
    for pat,topic in OFFICER:
        if pat.search(nm):
            # An AI/digital-officer programme necessarily covers AI governance;
            # count that as secondary coverage rather than leaving it uncounted.
            sec=LADDER
            if re.search(r'\bai\b|artificial intelligence|\bcaio\b|\bctaio\b|\bcdaio\b|digital',nm,re.I):
                sec="AI governance frameworks and operating models"
            return _byname_all[topic],_byname_all[sec],'officer-rule'
    for pat,topic in SECTOR:
        if pat.search(nm):
            return _byname_all[topic],'','sector-rule'
    return None

def norm_name(s):
    s=(s or '').lower()
    s=re.sub(r'\(.*?\)','',s)
    s=re.sub(r'\[.*?\]','',s)            # [Batch-22] style markers
    s=re.sub(r'batch[\s\-]*\d+|cohort\s*\d+|\b20\d\d\b|\b\d{1,2}(st|nd|rd|th)\b','',s)
    s=re.sub(r'\bbatch\b','',s)
    s=re.sub(r'[^a-z0-9 ]',' ',s); s=re.sub(r'\s+',' ',s).strip()
    return s

rows=[]
for f in sorted(glob.glob(f'{BASE}/data/catalogues/*.csv')):
    for r in csv.DictReader(open(f,encoding='utf-8')):
        if not (r.get('programme_name') or '').strip(): continue
        rows.append(r)

# dedupe: same school + same normalised name = one product; count runs
seen={}
for r in rows:
    k=(r['school_slug'], norm_name(r['programme_name']))
    if k in seen:
        seen[k]['_runs']+=1
        # keep richest record
        if len(str(r.get('key_topics','')))>len(str(seen[k].get('key_topics',''))):
            r['_runs']=seen[k]['_runs']; seen[k]=r
    else:
        r['_runs']=1; seen[k]=r
prods=list(seen.values())

def score(r):
    sc=collections.defaultdict(float)
    for field,w in WEIGHT.items():
        txt=(r.get(field) or '')
        if not txt: continue
        for pat,t in pats:
            if pat.search(txt): sc[t['topic_id']]+=w
    return sc

_tmap_all={t['topic_id']:t for t in tax}
out=[]
unmatched=[]
excluded=[]
for r in prods:
    blob=' '.join(str(r.get(k,'')) for k in ('programme_name','school_category','target_audience'))
    if EXCLUDE.search(blob) or MOOC.search(' '.join(str(r.get(k,'')) for k in ('partner','url','programme_name'))):
        excluded.append(r); continue
    pri=priority_topic(r)
    if pri:
        primary,secondary,conf=pri
        p=_tmap_all.get(primary)
        out.append(dict(
            school=r['school'], school_slug=r['school_slug'], region=r.get('region',''),
            programme_name=r['programme_name'], url=r.get('url',''),
            format=r.get('format',''), partner=r.get('partner',''),
            level=r.get('level',''), fee_currency=r.get('fee_currency',''),
            fee_amount=r.get('fee_amount',''), duration_days=r.get('duration_days',''),
            duration_weeks=r.get('duration_weeks',''), is_new=r.get('is_new_2025_26',''),
            scheduled_runs=r.get('_runs',1),
            school_category=r.get('school_category',''),
            channel=r.get('channel') or ('Partner' if (r.get('partner') or '').strip() else 'Direct'),
            mark=r.get('mark') or ('(P)' if (r.get('partner') or '').strip() else ''),
            theme=p['theme'], subtheme=p['subtheme'], topic=p['topic'], topic_id=primary,
            secondary_topic_id=secondary, ai_era_flag=p['ai_era_flag'],
            match_confidence=conf))
        continue
    sc=score(r)
    if not sc:
        # fallback pass on the name, then the category
        hit=None
        for pat,tid in FALLBACK:
            if pat.search(r.get('programme_name') or ''): hit=tid; break
        if not hit:
            for pat,tid in FALLBACK:
                if pat.search(r.get('school_category') or ''): hit=tid; break
        if hit:
            primary=hit; secondary=''; conf='fallback'
        else:
            unmatched.append(r); primary=secondary=None; conf='none'
    else:
        ranked=sorted(sc.items(),key=lambda x:-x[1])
        primary=ranked[0][0]; secondary=ranked[1][0] if len(ranked)>1 else ''
        top=ranked[0][1]
        conf='high' if top>=3 else ('medium' if top>=1.6 else 'low')
    tmap={t['topic_id']:t for t in tax}
    p=tmap.get(primary) if primary else None
    out.append(dict(
        school=r['school'], school_slug=r['school_slug'], region=r.get('region',''),
        programme_name=r['programme_name'], url=r.get('url',''),
        format=r.get('format',''), partner=r.get('partner',''),
        level=r.get('level',''), fee_currency=r.get('fee_currency',''),
        fee_amount=r.get('fee_amount',''), duration_days=r.get('duration_days',''),
        duration_weeks=r.get('duration_weeks',''), is_new=r.get('is_new_2025_26',''),
        scheduled_runs=r.get('_runs',1),
        school_category=r.get('school_category',''),
        channel=r.get('channel') or ('Partner' if (r.get('partner') or '').strip() else 'Direct'),
        mark=r.get('mark') or ('(P)' if (r.get('partner') or '').strip() else ''),
        theme=p['theme'] if p else 'UNCLASSIFIED', subtheme=p['subtheme'] if p else '',
        topic=p['topic'] if p else '', topic_id=primary or '',
        secondary_topic_id=secondary or '', ai_era_flag=p['ai_era_flag'] if p else '',
        match_confidence=conf))

with open(f'{BASE}/programmes_tagged.csv','w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=list(out[0].keys()),quoting=csv.QUOTE_ALL); w.writeheader(); w.writerows(out)

print(f"excluded (faculty dev/academic): {len(excluded)}")
print(f"rows in catalogues: {len(rows)}  distinct products: {len(prods)}  unclassified: {len(unmatched)}")
print("confidence:",dict(collections.Counter(o['match_confidence'] for o in out)))
print("\nproducts per school:")
for k,v in collections.Counter(o['school_slug'] for o in out).most_common():
    print(f"  {k:10s} {v}")
print("\nUNCLASSIFIED sample:")
for u in unmatched[:25]: print("   ",u['school_slug'],"|",u['programme_name'][:70])
print("\ntheme totals:")
for k,v in collections.Counter(o['theme'] for o in out).most_common(): print(f"  {v:4d}  {k}")

# --- the launch register, tagged with the same engine -----------------------
# So the dashboard can say which themes and levels other schools are launching
# into. A launch that is in the catalogue takes that programme's topic and
# level (the catalogue row has the curriculum and the school's own category to
# go on); one that is not is tagged on its name alone. The level is only ever
# what a page said or what the name states outright; otherwise it is Unknown.
_REG=f'{BASE}/data/peer_launches.csv'
_LSTOP={'the','and','of','in','for','with','programme','program','course','online','certificate','a','an','to',
        'batch','on','executive'}
def _ltok(n):
    n=re.sub(r'[^\w\s]',' ',re.sub(r'\(.*?\)',' ',(n or '').lower()))
    return {w for w in n.split() if len(w)>1 and w not in _LSTOP and not w.isdigit()}
_LEVEL_NAME=[
 (re.compile(r'\bchief\b|\bcxos?\b|\bc-?suite\b|\b(ceo|cfo|cmo|chro|coo|cto|cio)s?\b|senior leader|'
             r'senior executive|senior management|top management|advanced management',re.I),'C-suite/Senior'),
 (re.compile(r'\bboards?\b|\bboardroom\b|conseils d.administration|non-executive director',re.I),'Board'),
 (re.compile(r'emerging leader|young leader|first[- ]time manager|new manager|early[- ]career',re.I),'Early/Emerging'),
]
if os.path.exists(_REG):
    _bysc=collections.defaultdict(list)
    for o in out: _bysc[o['school_slug']].append(o)
    _tagged=[]
    for r in csv.DictReader(open(_REG,encoding='utf-8')):
        a=_ltok(r['programme']); best=None; bd=9
        if len(a)>=2 or any(len(w)>5 for w in a):
            for o in _bysc[r['school_slug']]:
                b=_ltok(o['programme_name'])
                if not (a-b) and len(b-a)<=1 and len(b-a)<bd: best,bd=o,len(b-a)
        if best and best['topic_id']:
            tid,tbasis=best['topic_id'],'catalogue'
        else:
            # a bracketed note is not the title: "(with the Financial Times)" is not finance
            rr={'programme_name':re.sub(r'\(.*?\)',' ',r['programme']).strip(),'school_slug':r['school_slug']}
            pri=priority_topic(rr); sc=score(rr) if not pri else None
            tid=pri[0] if pri else (max(sc.items(),key=lambda x:x[1])[0] if sc else
                 next((t for p,t in FALLBACK if p.search(rr['programme_name'])),''))
            tbasis='name' if tid else ''
        lv=(best or {}).get('level','') or ''
        lv='C-suite/Senior' if lv=='Senior' else lv
        lbasis='catalogue' if lv and lv!='Unknown' else ''
        if not lbasis:
            lv=next((l for p,l in _LEVEL_NAME if p.search(r['programme'])),'')
            lbasis='name' if lv else ''
        t=_tmap_all.get(tid,{})
        _tagged.append(dict(school_slug=r['school_slug'],programme=r['programme'],topic_id=tid,
            theme=t.get('theme',''),topic=t.get('topic',''),topic_basis=tbasis,level=lv or 'Unknown',level_basis=lbasis))
    with open(f'{BASE}/outputs/launches_tagged.csv','w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(_tagged[0].keys()),quoting=csv.QUOTE_ALL); w.writeheader(); w.writerows(_tagged)
    print(f"\nlaunch register tagged: {len(_tagged)} launches; "
          f"{sum(1 for x in _tagged if x['topic_basis']=='catalogue')} matched to a catalogue programme; "
          f"level known for {sum(1 for x in _tagged if x['level']!='Unknown')}")
