#!/usr/bin/env python3
"""Tags every captured programme to a taxonomy topic, deterministically.

Rebuildable: re-run after any catalogue refresh. Writes programmes_tagged.csv
(one row per distinct product per school) and the tagged launch register. The
rules are in scripts/classifier.py; scripts/check_classification.py tests them.
"""
import csv, os, re, glob, collections, json

import pathlib as _pl; BASE=str(_pl.Path(__file__).resolve().parent.parent)
from classifier import Classifier
CL=Classifier(_pl.Path(BASE))
tax=CL.tax
_tmap_all=CL.T


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

out=[]
unmatched=[]
excluded=[]
for r in prods:
    if CL.excluded(r):
        excluded.append(r); continue
    c=CL.classify(r)
    primary,secondary,conf=c['topic_id'],c['secondary_topic_id'],c['confidence']
    if not primary: unmatched.append(r)
    p=_tmap_all.get(primary) if primary else None
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
        match_confidence=conf, match_why=c['why']))

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
            tid=CL.classify(rr)['topic_id']
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
