#!/usr/bin/env python3
"""Builds site/data.json from the analysis outputs. Run after analyse.py and
demand_index.py. Keeping this separate from the page means a refresh rewrites
one JSON file and the HTML diff stays empty."""
import csv,json,glob,collections,pathlib
R=pathlib.Path(__file__).resolve().parent.parent
L=lambda p:list(csv.DictReader(open(R/p,encoding='utf-8')))
prog=L('programmes_tagged.csv'); tax=L('data/taxonomy.csv')
th=L('outputs/matrix_theme_by_school.csv'); sb=L('outputs/matrix_subtheme_by_school.csv')
tp=L('outputs/matrix_topic_full.csv'); g=L('outputs/gap_register.csv')
ai=L('outputs/ai_era_exposure_by_school.csv'); di=[r for r in L('outputs/demand_index.csv') if int(r['demand_index'])>0]
raw={}
for f in glob.glob(str(R/'data/catalogues/*.csv')):
    for r in csv.DictReader(open(f,encoding='utf-8')):
        raw.setdefault((r['school_slug'],r['programme_name'].strip()),r)
S=['isb','iima','iimb','iimc','iimk','iiml','hbs','imd','insead','lbs','wharton']
tot={s:sum(int(r[s]) for r in th) for s in S}
gv=lambda p,k:((raw.get((p['school_slug'],p['programme_name'].strip())) or {}).get(k,'') or '').strip()
clip=lambda s,n:(s[:n]+'…') if len(s)>n else s
progs=[{'i':i,'sc':p['school_slug'],'n':p['programme_name'],'t':p['topic_id'],'f':p['format'],
  'dr':clip(gv(p,'duration_raw'),60),'fr':clip(gv(p,'fee_raw'),46),'cur':p['fee_currency'],
  'amt':p['fee_amount'],'lv':p['level'],'pt':p['partner'],'ta':clip(gv(p,'target_audience'),200),
  'kt':clip(gv(p,'key_topics'),300),'u':p['url'],'nw':p['is_new'],'runs':int(p['scheduled_runs'] or 1),
  'conf':p['match_confidence'],'sec':p['secondary_topic_id'],'cat':clip(p['school_category'],120),
  'ch':p['channel'],'mk':p['mark']} for i,p in enumerate(prog) if p['theme']!='UNCLASSIFIED']
tree=collections.OrderedDict()
for t in tax: tree.setdefault(t['theme'],collections.OrderedDict()).setdefault(t['subtheme'],[]).append(
  {'id':t['topic_id'],'n':t['topic'],'ai':t['ai_era_flag']})
tpm={r['topic']:r for r in tp}; tmeta={}
for t in tax:
    r=tpm.get(t['topic'])
    if r: tmeta[t['topic_id']]={'dem':int(r['demand_score']),'srcs':int(r['demand_sources']),
      'geo':r['demand_geographies'],'resid':r['supply_is_residual_bucket']=='Y',
      'man':r['demand_is_manually_mapped']=='Y','sup':int(r['supply_incl_secondary']),
      'dsl':clip(r['demand_source_list'],240)}
tpi={r['topic_id']:r for r in tp}
d={'totals':tot,'schools':S,'asof':__import__('datetime').date.today().strftime('%d %b %Y'),
 'themes':[{'t':r['theme'],'isb':int(r['isb']),'ind':int(r['india_comp']),'glo':int(r['global_comp']),
   'dem':int(r['demand_sources']),'by':{s:int(r[s]) for s in S}} for r in th],
 'subs':[{'t':r['theme'],'st':r['subtheme'],'dem':int(r['demand_sources']),
   'isbAlso':int(r['isb_also_covers']),'peersAlso':int(r['peers_also_cover']),
   'by':{s:int(r[s]) for s in S}} for r in sb],
 'tree':tree,'tmeta':tmeta,'calls':{x['topic_id']:x['call'] for x in g},'progs':progs,
 'ai':[{'s':r['school'],'n':int(r['products']),'pct':float(r['ai_era_pct'])} for r in ai],
 'callrows':[{'call':x['call'],'theme':x['theme'],'topic':x['topic'],'tid':x['topic_id'],
   'ai':x['ai_era_flag'],'isb':int(x['isb']),'comp':int(x['supply_incl_secondary']),
   'dem':int(x['demand_score']),'geo':x['demand_geographies'],
   'resid':x['supply_is_residual_bucket']=='Y','man':x['demand_is_manually_mapped']=='Y',
   'srcs':int(x['demand_sources'])} for x in g],
 'scatter':[{'topic':r['topic'],'tid':r['topic_id'],'theme':r['theme'],'ai':r['ai_era_flag'],
   'sup':int(r['supply_incl_secondary']),'dem':int(r['demand_score']),'isb':int(r['isb']),
   'resid':r['supply_is_residual_bucket']=='Y'} for r in tp if int(r['demand_score'])>0 or int(r['supply_incl_secondary'])>0],
 'demand':sorted([{'t':x['topic'],'tid':x['topic_id'],'th':x['theme'],'idx':int(x['demand_index']),
   'out':int(x['outlook_2027_31']) if x['outlook_2027_31'] else 0,'why':x['outlook_rationale'],
   'src':int(x['sources']),'geo':int(x['geographies']),'sig':x['best_signal'],
   'dated':x['forward_dated']=='Y','contested':x['contested']=='Y','ai':x['ai_era_flag'],
   'isb':int(tpi.get(x['topic_id'],{}).get('isb',0)),
   'peers':int(tpi.get(x['topic_id'],{}).get('supply_incl_secondary',0))-int(tpi.get(x['topic_id'],{}).get('isb_incl_secondary',0))}
   for x in di],key=lambda z:-z['idx']),
 'demandMeta':{'signals':len(L('data/demand_all.csv')),'topics':len(di)}}
(R/'site'/'data.json').write_text(json.dumps(d,separators=(',',':'),ensure_ascii=False),encoding='utf-8')
print('site/data.json written:',len(json.dumps(d)),'bytes')
