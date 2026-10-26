#!/usr/bin/env python3
"""Validate our Buecker2023 extraction against gold, for the preliminary 10-paper run.

Two halves:
  (A) 6 study-level DESCRIPTORS (yearT1, country, Outcome_variable, sample_type,
      ethnicity, lag) scored against Jansen's human_coding_final 'Buecker2023' sheet,
      reported alongside Jansen's published LLM baseline accuracy per variable.
  (B) The N/M/SD numeric PAYLOAD scored by set-recall against the meta-analysts'
      own data_final rows (values Jansen never benchmarked) — our differentiator.

Usage:
  PYTHONPATH=src python scripts/validate_buecker_vs_jansen.py \
      --runs data/runs/jansen_buecker2023 [--studies Abele2016 ...]
"""
import argparse, json, re, unicodedata, zipfile, io
from collections import Counter
from pathlib import Path
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
from eval._paths import JANSEN_DIR, run_dir  # shipped locations of runs + third-party gold
JAR = JANSEN_DIR/'osfstorage-archive'/'coding_data.zip'
PAYLOAD_GOLD = REPO/'eval'/'buecker2023'/'gold_payload_100.csv'

# our study_id (from the reference-list filename) -> the human_coding_final 'study' label,
# for the few where they differ (spelling / year-of-publication drift / non-ASCII).
GOLD_ALIAS = {'Berghuis2020':'Borghuis2019', 'Bergold2024':'Bergold2021',
              'Bergman2009':'Bergmann2009', 'Busseri2013':'Busseri2012',
              'Buhler2020':'Bühler2020', 'Davis2019':'Davis2018',
              'Garcia-Pena2013':'GarcíaPeña2013', 'Ellberg2020':'Ellberg2019',
              'Eisman2017':'Eisman2015',
              # +49 batch (2026-07-08, Gerber..Li): accent/punct + year-off aliases (verified vs data_final ArtID)
              'Gomez-Baya2018':'GomezBaya2018',
              'Haraden2019':'Haraden2018', 'Helgeson2015':'Helgeson2014',
              'Hsu2009':'Hsu2014', 'Jackson2014':'Jackson2013',
              'Koivumaa-Honkanen2004':'KoivumaaHonkanen2004',
              'Koivumaa-Honkanen2005':'KoivumaaHonkanen2005',
              'Kuhlman2020':'Kuhlman2019', 'Lee2020':'Lee2019', 'Liem2010':'Liem2009',
              # Jansen's gold has CORRUPTED study labels for these two (letter transposition +
              # wrong year); verified same study by field-for-field match against our extraction.
              'Daukantaite2012':'Dankantaité2011',   # Dau->Dan, 2012->2011
              'Gustavson2016':'Gutsavson2015'}       # Gusta->Gutsa, 2016->2015
# ChenK2020 (K.-M. Chen, TDCYP) is the ONLY study with no gold anywhere in Jansen's data
# (absent from both human_coding_final and the LLM coding sheets) -> skipped for (A).
# Daukantaite2012 and Gustavson2016 DO have gold, under corrupted labels (see GOLD_ALIAS above).

# Jansen's published per-variable LLM baseline (d_acc_combined, meta==Buecker2023): mean accuracy.
JANSEN_BASELINE = {'yearT1':0.91,'country':0.88,'Outcome_variable':0.83,
                   'sample_type':0.77,'lag':0.64,'ethnicity':0.46}
JANSEN_MEAN = 0.75

# study-id (clean) -> human_coding 'study' label / payload 'Authors' prefix
STUDIES = ['Abele2016','Adamczyk2017','Adie2010','Allan2019','Anglim2015',
           'Armenta2014','Bares2012','Barker2016','Bearman2006','Berg2011',
           'Berghuis2020','Bergman2009','Bergold2024','Boer2022','Bratt2015',
           'Burger2017','Burr2011','Burris2017','Busseri2009','Busseri2013',
           'Buhler2020','Cappeliez2010','Carmel2015','Carmel2016','Casas2022',
           'Cebotari2018','Chen2009','Chen2020','ChenK2020','Cowan2019',
           # +10 (2026-07-07): alphabetical continuation Cowlishaw..Eijnden
           'Cowlishaw2013','Dainese2011','Daniel2016','Daukantaite2012','Davis2019',
           'Delfabbro2017','Dill2004','Duffy2011','Duineveld2017','Eijnden2018',
           # +10 (2026-07-08): Eisman..Garcia-Pena
           'Eisman2017','Ellberg2020','Eloranta2012','Esnaola2019','Fergusson2015',
           'Frison2016','FrizellReiter2016','Galla2020','Garcia2012','Garcia-Pena2013',
           # +49 batch (2026-07-08): Gerber..Li
           'Gerber2013','Gillham2011','Gomez-Baya2018','Gray2019','Griffith2021',
           'Gustavson2014','Gustavson2016','Haase2008','Haase2012','Hackett2019','Haraden2019',
           'Harding2013','Harris2017','Hatano2017','Hatano2022','Helgeson2015','Henning2019',
           'Hsu2009','IsikAkin2021','Jackson2014','Jiang2020','Jose2012','Jovanovic2019','Jung2017',
           'Kahana2013','Kanazawa2022','Kashima2015','Kasperzack2014','King2017','Kipp2015',
           'Knecht2017','Kohut2018','Koivumaa-Honkanen2004','Koivumaa-Honkanen2005',
           'Kokko2013','Kokko2018','Koletzko2015','Kramer2019','Ku2015','Kuhlman2020','Lachman2008',
           'Lee2014','Lee2020','Lemmens2011','Lent2015','Leung2004','Li2014',
           # +3 (2026-07-09): replace Goebel(SOEP outlier)+Kobayashi(JSON-trunc) -> 100
           'Liem2010','Lin2019','Marques2016']

_COUNTRY_ALIAS={'unitedstates':'usa','unitedstatesofamerica':'usa','us':'usa','america':'usa',
                'unitedkingdom':'uk','greatbritain':'uk','england':'uk',
                'thenetherlands':'netherlands','holland':'netherlands','korea':'southkorea',
                'republicofkorea':'southkorea'}
def norm(s):
    s=unicodedata.normalize('NFKD',str(s)).encode('ascii','ignore').decode().lower()
    s=re.sub(r'[^a-z0-9]','',s)
    return _COUNTRY_ALIAS.get(s,s)
def gnum(x):
    try: return float(re.sub(r'[^0-9.\-]','',str(x)))
    except: return None

# gold enum -> our schema vocab
ETH = {'1':'predominantly white/european','2':'predominantly black','3':'predominantly asian',
       '4':'predominantly hispanic/latin american','5':'predominantly native american',
       '6':'other','7':'not specified'}
# Buecker gold's ACTUAL sample_type scheme (verified against human_coding_final distinct values):
# 1=Nationally-representative, 2=Community(convenience), 3=College/university, 4=Other, 5=Not specified.
# NOTE: the gold has NO 'clinical/patient' category — our schema's clinical/patient can never match.
SAMP = {'1':'nationally-representative','2':'community/convenience',
        '3':'college/university students','4':'other','5':'not specified'}
OUT = {'1':'life satisfaction','2':'positive affect','3':'negative affect'}
def enum_code(v):  # "5 = Predominantly Native American" -> "5"
    m=re.match(r'\s*(\d)',str(v)); return m.group(1) if m else None

def load_gold_descriptors():
    with zipfile.ZipFile(JAR) as z:
        hum=pd.read_excel(io.BytesIO(z.read('coding_data/human_coding_final.xlsx')),
                          sheet_name='Buecker2023').astype(object)
    hum['study']=hum['study'].map(lambda s: s if isinstance(s,str) else None)
    gold={}
    for st in STUDIES:
        rows=hum[hum['study']==GOLD_ALIAS.get(st,st)]
        if len(rows)==0: continue
        def modal(col):
            # DETERMINISTIC modal. The old `max(set(vals), key=vals.count)` broke ties by
            # set-iteration order, which is hash-seed dependent -> the gold (and therefore every
            # metric) changed run-to-run. Ties are now broken by the smallest string repr.
            vals=[v for v in rows[col].tolist() if v==v and v is not None]
            if not vals: return None
            cnt=Counter(vals); top=max(cnt.values())
            return sorted((v for v,c in cnt.items() if c==top), key=lambda x: str(x))[0]
        outs={OUT.get(enum_code(v)) for v in rows['Outcome_variable'].tolist() if enum_code(v)}
        gold[st]=dict(
            yearT1=gnum(modal('yearT1')),
            country=norm(modal('country')),
            Outcome_variable={o for o in outs if o},
            sample_type=SAMP.get(enum_code(modal('sample_type'))),
            ethnicity=ETH.get(enum_code(modal('ethnicity'))),
            lag=gnum(modal('lag')) if not isinstance(modal('lag'),str) or re.match(r'^[\d.]+$',str(modal('lag'))) else None,
        )
    return gold

def load_gold_payload():
    df=pd.read_csv(PAYLOAD_GOLD)  # study_id-keyed (all 20)
    gold={}
    for st in STUDIES:
        rows=df[df['study_id']==st]
        gold[st]=dict(
            M={round(float(v),2) for v in rows['M'].tolist() if v==v},
            SD={round(float(v),2) for v in rows['SD'].tolist() if v==v},
            N={int(v) for v in rows['N'].tolist() if v==v},
        )
    return gold

def load_extraction(runs, st):
    p=Path(runs)/st/'paper_target.json'
    if not p.exists(): return None
    return json.loads(p.read_text())

def flat(v):
    """paper-scope -> scalar; sample-scope {key:[vals]} -> flattened value list."""
    if isinstance(v,dict):
        out=[]
        for vals in v.values():
            if isinstance(vals,list): out+=[x for x in vals if x not in (None,'None','')]
            elif vals not in (None,'None',''): out.append(vals)
        return out
    return v

def close(a,b,tol,rel=False):
    if a is None or b is None: return False
    if rel: return abs(a-b)<=tol*max(abs(b),1e-9)
    return abs(a-b)<=tol

def num_recall(gold_set, ext_vals, tol, rel=False):
    ext=[gnum(x) for x in ext_vals if gnum(x) is not None]
    hit=sum(1 for g in gold_set if any(close(e,g,tol,rel) for e in ext))
    return hit, len(gold_set), len(ext)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--runs',default='data/runs/jansen_buecker2023')
    ap.add_argument('--studies',nargs='*',default=None)
    a=ap.parse_args()
    studies=a.studies or STUDIES
    gd=load_gold_descriptors(); gp=load_gold_payload()

    # ---- (A) descriptors ----
    fields=['yearT1','country','Outcome_variable','sample_type','ethnicity','lag']
    hits={f:0 for f in fields}; tot={f:0 for f in fields}; present=[]
    for st in studies:
        ext=load_extraction(a.runs,st)
        if ext is None: continue
        present.append(st)
        g=gd.get(st,{})
        for f in fields:
            gv=g.get(f)
            if gv is None or (isinstance(gv,set) and not gv): continue
            tot[f]+=1
            ev=ext.get(f)
            if f=='Outcome_variable':
                if isinstance(ev,dict): raw=flat(ev)
                elif isinstance(ev,str): raw=re.split(r'[;,]',ev)          # comma-joined multi_label string
                elif isinstance(ev,list): raw=ev
                else: raw=[]
                es={norm(x) for x in raw if x and norm(x)}
                gs={norm(x) for x in gv}
                if gs and len(gs & es)/len(gs)>=0.5: hits[f]+=1
            elif f in ('yearT1',):
                if close(gnum(ev),gv,1): hits[f]+=1
            elif f=='lag':
                if close(gnum(ev),gv,0.34): hits[f]+=1
            else:  # country, sample_type, ethnicity
                if norm(ev)==norm(gv): hits[f]+=1

    print(f"\n{'='*70}\nBUECKER2023 PRELIMINARY VALIDATION — {len(present)}/{len(studies)} papers extracted")
    print(f"papers: {', '.join(present) or '(none yet)'}\n{'='*70}")
    print("\n(A) DESCRIPTORS vs Jansen human_coding gold  [ours acc | Jansen baseline]")
    print(f"{'field':20s} {'n':>3} {'ours':>6}   {'Jansen':>6}")
    oa=[]
    for f in fields:
        if tot[f]==0: print(f"{f:20s}   0      -        {JANSEN_BASELINE[f]:.2f}"); continue
        acc=hits[f]/tot[f]; oa.append(acc)
        print(f"{f:20s} {tot[f]:>3} {acc:>6.2f}   {JANSEN_BASELINE[f]:>6.2f}")
    if oa:
        print(f"{'MEAN':20s}     {sum(oa)/len(oa):>6.2f}   {JANSEN_MEAN:>6.2f}")

    # ---- (B) numeric payload (set-recall) ----
    print("\n(B) NUMERIC PAYLOAD set-recall vs data_final  (M ±2%, SD ±0.05, N exact) — Jansen did NOT benchmark these")
    print(f"{'study':14s} {'M(hit/gold,ext)':>18} {'SD(hit/gold,ext)':>18} {'N(hit/gold,ext)':>18}")
    agg={'M':[0,0],'SD':[0,0],'N':[0,0]}
    for st in present:
        ext=load_extraction(a.runs,st); g=gp.get(st,{})
        mh,mg,me=num_recall(g.get('M',set()), flat(ext.get('M_SWB',{})), 0.02, rel=True)
        sh,sg,se=num_recall(g.get('SD',set()), flat(ext.get('SD_SWB',{})), 0.05)
        nh,ng,ne=num_recall(g.get('N',set()), flat(ext.get('Sample',{})), 1)
        agg['M'][0]+=mh;agg['M'][1]+=mg;agg['SD'][0]+=sh;agg['SD'][1]+=sg;agg['N'][0]+=nh;agg['N'][1]+=ng
        print(f"{st:14s} {f'{mh}/{mg},{me}':>18} {f'{sh}/{sg},{se}':>18} {f'{nh}/{ng},{ne}':>18}")
    for k in ('M','SD','N'):
        h,t=agg[k]; print(f"  {k} overall recall: {h}/{t} = {h/t:.2f}" if t else f"  {k}: no gold")

if __name__=='__main__':
    main()
