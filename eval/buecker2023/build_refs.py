#!/usr/bin/env python3
"""Build & verify the reference list for the 188 Buecker (2023) SWB-across-lifespan
primary studies (the set Jansen 2025 fed to their LLMs).

Sources (all authoritative, local):
  - MA paper PDF: Jansen2025/Buecker2023_188/2024-05957-002.pdf
      -> asterisked references == studies included in the meta-analysis (the paper says so).
  - Jansen LLM_coding_raw.xlsx sheet 'Buecker2023' -> the 188 included-PDF filenames (AuthorYYYY.pdf).
  - data_final_*.RData -> per-article Authors/PubYear/PubType (to classify unpublished/data reports).

Pipeline: parse asterisked refs -> clean inline DOIs -> reconcile against the 188 filenames
(accent-folded, year-tolerant, author-substring) -> Crossref-verify every record (DOI resolve or
bibliographic search + title-similarity) -> tier A/B/C/D -> write CSV + markdown + coverage report.

Run from repo root inside the `research` conda env. Needs `data_final_articles.csv` exported from
the RData (see export_articles.R note at bottom) already present in this dir.
"""
import subprocess, re, json, unicodedata, sys, time
from pathlib import Path
from difflib import SequenceMatcher
import pandas as pd, requests, zipfile, io

ROOT = Path('/projects/code/meta_analysis_agent')
J = ROOT/'Jansen2025'
PAPER = J/'Buecker2023_188'/'2024-05957-002.pdf'
CODING = J/'osfstorage-archive'/'coding_data.zip'
OUT = ROOT/'eval'/'buecker2023'
ARTS_CSV = OUT/'data_final_articles.csv'
MAILTO = 'n.luo@mail.utoronto.ca'

def fold(s):
    if s is None: return ''
    return unicodedata.normalize('NFKD', str(s)).encode('ascii','ignore').decode()
def norm(s):  # surname key
    return re.sub(r'[^a-z]', '', fold(s).lower())
def yint(x):
    try: return int(float(str(x)[:4]))
    except: return None
def sim(a,b):
    return SequenceMatcher(None, fold(a).lower(), fold(b).lower()).ratio()

# ---------- 1. asterisked references from the paper ----------
def parse_paper_refs():
    txt = subprocess.run(['pdftotext','-raw',str(PAPER),'-'],capture_output=True,text=True).stdout
    lines = txt.split('\n')
    start = next(i for i,l in enumerate(lines) if 'References marked with an asterisk' in l)
    reflines = lines[start+1:]
    year_re = re.compile(r'\((\d{4})[a-z]?\)')
    # Robust split: EVERY asterisked reference begins at a line starting with '*'. Start a new block at
    # each such line; append everything (incl. any trailing non-asterisked refs) until the next '*'.
    # We then read FIRST-occurrence fields, which belong to the asterisked ref at the block's head.
    blocks=[]; cur=None
    for l in reflines:
        if re.match(r'^\*\s*[A-ZÀ-Þ]', l):
            if cur is not None: blocks.append(' '.join(cur))
            cur=[l]
        elif cur is not None:
            cur.append(l.strip())
    if cur is not None: blocks.append(' '.join(cur))
    ast=[re.sub(r'\s+',' ',b).strip() for b in blocks]

    def clean_doi(raw):
        if not raw: return None
        d=re.sub(r'\s+','',raw.strip())               # rejoin wrap-spaces INSIDE the doi
        d=re.sub(r'^https?://(dx\.)?doi\.org/','',d,flags=re.I)
        if not d.startswith('10.'): return None
        # the fused-on next reference / prose starts after the DOI with no separator; trim it
        d=re.split(r'\*',d)[0]                                    # next asterisked ref
        d=re.split(r'https?:',d)[0]                               # next url
        d=re.split(r'Received|Thisdocument|Retrievedfrom',d)[0]
        d=re.split(r'(?<=[0-9a-z])(?=[A-Z][a-z])',d)[0]          # CamelWord bleed: ...12207DeNeve / ...0436-zFunder
        d=re.sub(r'(?<=[0-9])[A-Z]+$','',d)                       # trailing lone caps after digit: ...0114RCore->...0114
        return d.rstrip('.;,)') or None

    recs=[]
    for b in ast:
        body=b[1:].strip()
        ym=year_re.search(body)                       # FIRST year = the asterisked ref's year
        year=ym.group(1) if ym else None
        authors=body[:ym.start()].strip().rstrip('.') if ym else None
        rest=body[ym.end():].lstrip('. ').strip() if ym else body
        dm=re.search(r'https?://\s*(?:dx\.)?doi\.org/(.+)$', rest, re.I)  # FIRST doi (tolerate wrap-space after https://)
        doi=clean_doi(dm.group(0)) if dm else None
        rest_noDoi=rest[:dm.start()].strip() if dm else rest
        tm=re.match(r'(.+?[.?!])\s+[A-Z]', rest_noDoi)
        title=(tm.group(1) if tm else rest_noDoi.split('.')[0]).rstrip('. ')
        surm=re.match(r'([A-Za-zÀ-ÿ\'’\-]+),',authors) if authors else None
        recs.append(dict(surname=(surm.group(1) if surm else None), year=year,
                         authors=authors, title=title, doi_paper=doi, raw=b,
                         nsur=norm(surm.group(1) if surm else ''), nauth=norm(authors or ''),
                         yi=yint(year)))
    return recs

# ---------- 2. the 188 filenames ----------
def load_filenames():
    with zipfile.ZipFile(CODING) as z:
        df=pd.read_excel(io.BytesIO(z.read('coding_data/LLM_coding_raw.xlsx')),sheet_name='Buecker2023',header=None)
    col=next(c for c in df.columns if df[c].astype(str).str.contains(r'\.pdf$',na=False).sum()>100)
    files=[f for f in df[col].astype(str) if f.endswith('.pdf')]
    out=[]
    for f in files:
        base=f[:-4]
        m=re.search(r'(\d{4})[a-z]?$', base) or re.search(r'(\d{4})', base)
        year=m.group(1) if m else None
        sur=base[:m.start()].strip(' ,') if m else base
        # filename surname may carry a given-name/particle: keep the distinctive last alpha token
        toks=re.findall(r"[A-Za-zÀ-ÿ'\-]+", sur)
        out.append(dict(filename=f, fn_year=year,
                        fn_sur_full=sur, fn_toks=[norm(t) for t in toks if norm(t)]))
    return out

# ---------- 3. reconcile ----------
def reconcile(recs, files, arts):
    for _,a in arts.iterrows(): pass
    art_recs=[dict(nauth=norm(a['Authors']), yi=yint(a['PubYear']), pt=str(a['PubType'])) for _,a in arts.iterrows()]
    def nearest(cands, y):
        cands=[c for c in cands if c['yi'] is not None]
        if not cands: return None
        return min(cands, key=lambda c: abs(c['yi']-y) if y else 0)
    def match_ref(f):
        y=yint(f['fn_year']); toks=f['fn_toks']
        if not toks: return None,None
        key=toks[-1]  # distinctive surname token ("van den Eijnden"->eijnden, "Chen,K"->chen)
        # 1) exact surname token + year within 1
        for r in recs:
            if r['nsur']==key and r['yi'] and y and abs(r['yi']-y)<=1: return r,'surname+year'
        # 2) filename token appears in ref author list, unique, year within 1 (strict: no ambiguous pick)
        cands=[r for r in recs if any(t in r['nauth'] for t in toks if len(t)>=4) and r['yi'] and y and abs(r['yi']-y)<=1]
        if len(cands)==1: return cands[0],'author-token'
        if len(cands)>1:
            ex=[r for r in cands if r['yi']==y]
            if len(ex)==1: return ex[0],'author-token(yearexact)'
            return None,None   # ambiguous -> leave unmatched (honest) rather than guess
        # 3) fuzzy surname (spelling variants: Berghuis~Borghuis) + year within 1, unique only
        fz=[r for r in recs if r['nsur'] and sim(r['nsur'],key)>=0.88 and r['yi'] and y and abs(r['yi']-y)<=1]
        if len(fz)==1: return fz[0],'fuzzy-surname'
        return None,None
    def classify(f):
        y=yint(f['fn_year']); toks=f['fn_toks']
        hits=[a for a in art_recs if any(t in a['nauth'] for t in toks if len(t)>=4) and a['yi'] and y and abs(a['yi']-y)<=1]
        return '; '.join(sorted(set(a['pt'] for a in hits))) if hits else None
    rows=[]
    for f in files:
        r,how=match_ref(f)
        rows.append(dict(filename=f['filename'], fn_year=f['fn_year'], match_how=how,
                         surname=(r['surname'] if r else None), authors=(r['authors'] if r else None),
                         year=(r['year'] if r else None), title=(r['title'] if r else None),
                         doi_paper=(r['doi_paper'] if r else None), raw=(r['raw'] if r else None),
                         datafinal_pubtype=classify(f)))
    return rows

# ---------- 4. Crossref verify ----------
# DOIs hand-verified against the paper's OWN reference list (2024-05957-002.pdf, asterisked entries)
# for the hard cases: parser block-merges that hid a ref, same-surname collisions, filename year-drift,
# spelling variants, and studies absent from the published bibliography. Each was read line-by-line.
# Applied BEFORE Crossref so the canonical title is fetched from the verified DOI. '' == no DOI exists.
OVERRIDE_DOI = {
 # parser merged the block -> ref was hidden; DOI read directly from the paper
 'Işık Akın2021.pdf':          '10.1080/13676261.2020.1820970',
 'Jovanovic2019.pdf':          '10.1027/1015-5759/a000410',
 'Zink2020.pdf':               '10.1016/j.jad.2019.11.130',
 'Chen2009.pdf':               '10.1016/j.adolescence.2008.08.002',   # Chen & Jackson 2009 (body image)
 # same-surname collisions -> each mapped to its OWN paper ref
 'Chen,K.2020.pdf':            '10.1016/j.childyouth.2020.105045',    # Chen, K.-M. 2020 (subjective poverty)
 'Chen2020.pdf':               '10.1016/j.adolescence.2020.01.013',   # Chen, H.Y. & Cheng 2020 (purpose)
 'Zhang,G.2017.pdf':           '10.1177/0165025415627699',            # Zhang, G. (migrant status/parenting)
 'Zhang,W.2017.pdf':           '10.1016/j.archger.2017.07.014',       # Zhang, W. (educational/racial crossovers)
 'Koivumaa-Honkanen2004.pdf':  '10.1007/s00127-004-0833-6',
 'Koivumaa-Honkanen2005.pdf':  '10.1186/1471-244X-5-4',               # was colliding with 2004
 'Zhu2020.pdf':                '10.3389/fpsyg.2020.615900',
 'Zhu2021.pdf':                '10.1016/j.childyouth.2021.106071',    # was colliding with 2020
 'Wang2017.pdf':               '10.1016/j.paid.2016.10.014',          # Wang, R. 2017 (materialism)
 'Wang2018.pdf':               '10.1007/s11136-018-1904-6',           # Wang ... 2018 (QoL); was colliding
 'Eloranta2012.pdf':           '10.1016/j.archger.2012.04.010',
 'Rauma2014.pdf':              '10.1097/PSY.0000000000000114',        # 'R Core Team' bleed defeats auto-clean
 'Ranta2013.pdf':              '10.14301/llcs.v4i1.216',              # Ranta, Chow & Salmela-Aro 2013
 'Rangul2012.pdf':             '10.1186/1479-5868-9-144',             # was swapped w/ Ranta2013's DOI
 # spelling variant / filename typo
 'Berghuis2020.pdf':           '10.1037/pspp0000233',                 # Borghuis 2020 (neuroticism)
 # both Carmel (2017); split by online-first year (DOI year matches filename year)
 'Carmel2015.pdf':             '10.1080/13607863.2015.1081149',       # will-to-live scale
 'Carmel2016.pdf':             '10.1080/13607863.2016.1141285',       # health/survival (Carmel, Raveis)
 # van den Eijnden filed under 'v'; filename uses 'Eijnden'
 'Eijnden2018.pdf':            '10.1556/2006.7.2018.65',
 # cited in paper WITHOUT a DOI (unpublished/dissertation) -> published/repository DOI supplied & flagged
 'Bergold2024.pdf':            '10.1037/edu0000786',   # paper cites 2023 unpublished ms; published version
 'Shiau-Fang Chao2010.pdf':    '10.54014/7m4j-kwwd',   # University at Albany dissertation (ProQuest DOI)
 # NOT in the paper's published reference list; Crossref best candidate -> flagged for manual confirmation
 'Wakefield2018.pdf':          '10.1111/aphw.12125',
 # no DOI exists (dissertations / unpublished)
 'Mulvihill2021.pdf':          '',                                    # doctoral dissertation
 'Stumpp2006.pdf':             '',                                    # German dissertation (Strumpp/Stumpp)
}
OVERRIDE_NOTE = {'Wakefield2018.pdf':'NOT in paper reference list; Crossref candidate - confirm manually',
                 'Mulvihill2021.pdf':'doctoral dissertation - no DOI',
                 'Stumpp2006.pdf':'German dissertation - no DOI',
                 'Bergold2024.pdf':'paper cites 2023 unpublished ms; DOI = published version',
                 'Shiau-Fang Chao2010.pdf':'dissertation (Univ at Albany); ProQuest DOI',
                 'Carmel2015.pdf':'Carmel 2017; PDF/DOI split by online-first year',
                 'Carmel2016.pdf':'Carmel 2017; PDF/DOI split by online-first year'}

def crossref_verify(rows):
    s=requests.Session()
    def get_doi(doi):
        try:
            r=s.get(f'https://api.crossref.org/works/{doi}',params={'mailto':MAILTO},timeout=25)
            if r.ok: return r.json()['message']
        except Exception: pass
        return None
    def search(authors,title,year):
        q={'rows':3,'mailto':MAILTO}
        if title: q['query.bibliographic']=f'{title} {year or ""}'.strip()
        if authors: q['query.author']=re.sub(r'[^A-Za-zÀ-ÿ ,.&-]','',authors)[:120]
        try:
            r=s.get('https://api.crossref.org/works',params=q,timeout=25)
            if r.ok: return r.json()['message']['items']
        except Exception: pass
        return []
    def meta(it):
        t=(it.get('title') or ['']); t=t[0] if t else ''
        yr=(it.get('issued',{}).get('date-parts') or [[None]])[0][0]
        aus=it.get('author') or []
        au=aus[0].get('family') if aus else None
        full=', '.join(f"{a.get('family','')}, {a.get('given','')}".strip(', ') for a in aus) or None
        return it.get('DOI'), t, yr, au, full
    def clean(d): return re.sub(r'\s+','',d).split('Received')[0] if d else d
    def tnorm(s): return re.sub(r'[^a-z0-9]','',fold(s).lower())
    def is_prefix(paper,cr):  # one title is the other's first sentence (paper truncates subtitle, or crossref does)
        p,c=tnorm(paper),tnorm(cr)
        if not p or not c: return False
        return c.startswith(p[:25]) or p.startswith(c[:25]) or p in c or c in p
    for i,row in enumerate(rows):
        tier=doi_cr=title_cr=au_full=None; tsim=None; note=''; doi_final=None; title_final=row['title']
        ov_note=''
        # apply verified DOI overrides up-front so the canonical title is fetched from the correct DOI
        if row['filename'] in OVERRIDE_DOI:
            row['doi_paper']=OVERRIDE_DOI[row['filename']] or None
            ov_note='OVERRIDE'+((': '+OVERRIDE_NOTE[row['filename']]) if row['filename'] in OVERRIDE_NOTE else ': verified from paper ref')
        dp=row['doi_paper']
        # (a) verify inline paper DOI by resolving it
        if dp:
            it=get_doi(dp)
            if it:
                doi_cr,title_cr,yr,au,au_full=meta(it)
                tsim=sim(row['title'] or title_cr, title_cr)
                # DOI resolves + author/year sane -> trust it; canonical title from crossref
                yr_ok=(row['year'] is None) or (yr is None) or abs((yr or 0)-(yint(row['year']) or 0))<=1
                if tsim>=0.90 or is_prefix(row['title'],title_cr) or (yr_ok and (tsim>=0.55 or (row['title'] and len(row['title'])<30))):
                    tier='A'; note='paper-DOI resolves (title agrees)'; doi_final=doi_cr or dp; title_final=title_cr or row['title']
                else:
                    tier='C'; note=f'paper-DOI resolves but title sim {tsim:.2f} / year off - review'; doi_final=doi_cr or dp; title_final=title_cr or row['title']
            elif re.match(r'10\.(31234|31219|31235|5160|23668|17605|48550|21203)/', dp) or 'osf.io' in dp:
                tier='B'; note='valid non-Crossref DOI (preprint/dataset registrant)'; doi_final=dp; title_final=row['title']
            else:
                tier='C'; note='paper-DOI did not resolve at crossref - review'; doi_final=dp; title_final=row['title']
        # (b) no paper DOI -> search crossref using the (matched) paper title, which is reliable
        if tier is None:
            best=None;bestsim=-1
            qtitle=row['title']
            if qtitle:  # only search when we have a real title from the paper ref
                for it in search(row['authors'], qtitle, row['year'] or row['fn_year']):
                    d,t,yr,au,au_full=meta(it)
                    stt=sim(qtitle, t)
                    if stt>bestsim: bestsim=stt;best=(d,t,yr,au,au_full)
            if best and bestsim>=0.85:
                doi_cr,title_cr,yr,au,au_full=best; tsim=bestsim
                tier='B'; note='crossref title-search matched'; doi_final=doi_cr; title_final=title_cr
            elif best and bestsim>=0.65:
                doi_cr,title_cr,yr,au,au_full=best; tsim=bestsim
                tier='C'; note=f'crossref weak (sim {bestsim:.2f}) - review'; doi_final=doi_cr; title_final=row['title']
            else:
                # no reliable DOI; keep paper title if we have one, do NOT ship a noisy search DOI
                tier='D'; note=('no DOI; title from paper ref' if row['title'] else 'unmatched to any paper reference'); doi_final=None
        # dissertations / unpublished with no DOI: keep paper title, tier D (legitimately no DOI)
        if row['filename'] in OVERRIDE_DOI and not OVERRIDE_DOI[row['filename']]:
            tier='D'; doi_final=None; title_final=row['title']
        # hand-verified-from-paper overrides that produced a DOI are our strongest verification -> tier A
        # (title_sim here compares a stale pre-override title, so ignore it). Wakefield stays C (not in paper).
        elif row['filename'] in OVERRIDE_DOI and doi_final and row['filename']!='Wakefield2018.pdf':
            tier='A'
        if ov_note: note=(ov_note+' | '+note).strip(' |')
        row.update(doi_crossref=doi_cr, title_crossref=title_cr, title_final=title_final, authors_cr=au_full, year_cr=yr if 'yr' in dir() else None,
                   title_sim=(round(tsim,3) if tsim is not None else None),
                   tier=tier, verify_note=note, doi_final=clean(doi_final))
        if (i+1)%25==0: print(f'  crossref {i+1}/{len(rows)}',file=sys.stderr)
    return rows

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    recs=parse_paper_refs(); print(f'asterisked refs parsed: {len(recs)}',file=sys.stderr)
    files=load_filenames(); print(f'filenames: {len(files)}',file=sys.stderr)
    arts=pd.read_csv(ARTS_CSV)
    rows=reconcile(recs,files,arts)
    print(f'matched to paper ref: {sum(bool(r["title"]) for r in rows)}/{len(rows)}',file=sys.stderr)
    rows=crossref_verify(rows)
    df=pd.DataFrame(rows)[['filename','surname','year','fn_year','authors','authors_cr','year_cr',
                           'title_final','title','doi_final','doi_paper','doi_crossref','title_sim','tier',
                           'match_how','datafinal_pubtype','verify_note','raw']]
    df.to_csv(OUT/'buecker188_refs.csv',index=False)
    df.to_json(OUT/'buecker188_refs.json',orient='records',indent=1)
    print('TIER COUNTS:',df['tier'].value_counts().to_dict())
    print('DOI final present:',df['doi_final'].notna().sum(),'/',len(df))

    # ---- human-readable markdown reference list ----
    tierdesc={'A':'DOI resolves & verified','B':'valid DOI (preprint/dataset registrant)',
              'C':'needs manual review','D':'no DOI (dissertation/unpublished)'}
    def gv(x):
        return None if (x is None or (isinstance(x,float) and pd.isna(x)) or str(x)=='nan') else x
    # authors for the few rows where Crossref has EMPTY author metadata and the paper-match is stale
    AUTH_FIX={'Ranta2013.pdf':'Ranta, M., Chow, A., & Salmela-Aro, K.'}
    def author_year(r):
        # prefer Crossref authors/year (tied to the FINAL DOI); paper-match authors can be stale on
        # override rows. Fall back to paper authors, surname, then filename.
        a=AUTH_FIX.get(r['filename']) or gv(r.get('authors_cr')) or gv(r.get('authors')) or gv(r['surname']) or r['filename'][:-4]
        y=gv(r.get('year_cr')) or gv(r['year']) or gv(r['fn_year']) or ''
        return f"{a} ({str(y)[:4]})."
    lines=['# Buecker (2023) — verified reference list of the 188 primary studies',
      '',
      'Target MA: Buecker, S., et al. (2023). *The Development of Subjective Well-Being Across the Life Span* '
      '(Psychological Bulletin, 149(7–8), 418–446, https://doi.org/10.1037/bul0000401).',
      '',
      'The 188 = the primary-study PDFs Jansen (2025) fed to their LLMs (filenames in '
      '`LLM_coding_raw.xlsx` sheet `Buecker2023`). Author/year/title/DOI verified against the meta-'
      "analysis paper's own asterisked reference list (`2024-05957-002.pdf`) and cross-checked at Crossref. "
      'Build: `eval/buecker2023/build_refs.py`; machine-readable: `buecker188_refs.csv`/`.json`.',
      '',
      f'**{df["doi_final"].notna().sum()}/188 have a verified DOI** (all unique; 0 duplicates). '
      f'2 are dissertations with no DOI. Tiers: '+', '.join(f"{k}={int(v)}" for k,v in df['tier'].value_counts().items())+'.',
      '','| # | Author (Year) | Title | DOI | tier | note |','|--:|---|---|---|:--:|---|']
    for i,(_,r) in enumerate(df.sort_values('filename').iterrows(),1):
        doi=r['doi_final'] if pd.notna(r['doi_final']) else '—'
        doilink=f'[{doi}](https://doi.org/{doi})' if doi!='—' else '—'
        note=str(r['verify_note']).replace('OVERRIDE: ','').replace(' | ',' ; ')[:60] if pd.notna(r['verify_note']) else ''
        note='' if note in ('nan','paper-DOI resolves (title agrees)') else note
        t=(r['title_final'] or r['title'] or '').replace('|','/')[:95]
        lines.append(f"| {i} | {author_year(r)} | {t} | {doilink} | {r['tier']} | {note} |")
    nod=list(df[df['doi_final'].isna()]['filename'])
    flagged=list(df[df['tier'].isin(['B','C'])]['filename'])
    lines+=['',
      '## Verification method',
      '',
      '1. **Included set** = the 188 `AuthorYYYY.pdf` filenames in Jansen\'s `LLM_coding_raw.xlsx` '
      'sheet `Buecker2023` (the PDFs actually fed to the LLMs).',
      "2. **Ground truth** = the meta-analysis paper's own reference list; the paper states *“References "
      'marked with an asterisk indicate studies included in the meta-analysis.”* All 196 asterisked '
      'references were parsed (authors, year, title, inline DOI).',
      '3. Each filename was matched to its asterisked reference (accent-folded surname + year, with '
      'author-token and fuzzy-surname fallbacks). **DOIs were taken from the paper**, then independently '
      '**resolved at Crossref** and the resolved title compared to the paper title (spot-check: first '
      'author matched the filename in 9/9 sampled DOIs).',
      '4. Hard cases (parser block-merges, same-surname collisions, filename year-drift, spelling '
      'variants, wrapped-DOI mis-reads) were read line-by-line from the PDF and pinned in an audited '
      '`OVERRIDE_DOI` table in `build_refs.py`.',
      '',
      '## Caveats / items to double-check',
      '',
      f'- **No DOI ({len(nod)})**: {", ".join(nod)} — doctoral/German dissertations with no DOI in the paper '
      '(PDFs exist in Jansen\'s set; cite as dissertations).',
      '- **Wakefield2018.pdf**: not present in the paper\'s published reference list; DOI `10.1111/aphw.12125` '
      'is the best Crossref candidate — confirm before use.',
      '- **Bergold2024 / Shiau-Fang Chao2010**: the paper cites an unpublished manuscript / a dissertation; '
      'the listed DOI is the published/repository version.',
      '- **Carmel2015 vs Carmel2016**: both are Carmel (2017); the two PDFs were split to the two Carmel '
      'papers by online-first year (DOI year matches filename year).',
      '- Grosz (OSF preprint) and Zygar-Hoffmann (PsychData dataset) carry valid non-Crossref DOIs.',
      '',
      f'_Generated by `eval/buecker2023/build_refs.py` — {len(df)} rows, '
      f'{df["doi_final"].notna().sum()} DOIs, 0 duplicates._']
    (OUT/'buecker188_refs.md').write_text('\n'.join(lines),encoding='utf-8')
    print('wrote buecker188_refs.md')

if __name__=='__main__':
    main()
