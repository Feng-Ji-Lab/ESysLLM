"""Unified Bowes extractor: read each paper ONCE and emit ALL 9 Jansen variables
together — study-level (YearOfPub, CTType, COVID), per-sample (N, female%,
recruitment), and per-effect-size (outcome, es, N). Outcome (study-level) is the
union of the effect-size outcomes, so it is derived, not asked twice.

Single-pass by design: every variable lives in the same correlation matrix /
demographics table, so one read keeps them mutually consistent (sample N matches
its effect sizes; the construct set matches the matrix) and halves the API cost
vs reading the paper twice.

OUR METHOD vs Jansen: input is Marker markdown + per-table TEXT GRIDS + the table
IMAGES (multimodal), with explicit "read the conspiracy row/column" guidance,
scale->token mapping, per-sample attribution, and evidence capture. Jansen used
PyPDF2 plaintext (es accuracy ~0.16-0.26); reading the table image+grid should
beat it. Jansen's verbatim effect-size prompt is kept at
schemas/bowes2023/jansen_effectsize_prompt.txt for an optional ablation.

Output: data/runs/jansen_bowes2023/<paper>/extraction.json
  {"conspiracy_measure", "study":{...}, "samples":[...], "effect_sizes":[...], "_meta":{...}}

Usage:
  source /projects/envs/miniconda3/etc/profile.d/conda.sh && conda activate research
  PYTHONPATH=src python scripts/extract_bowes.py
  PYTHONPATH=src python scripts/extract_bowes.py --only Betsch2018
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from mag.preprocessing.manifest_normalizer import normalize_manifests
from mag.preprocessing.section_builder import build_sections
from mag.providers.base import Asset as WireAsset
from mag.providers.gemini import GeminiProvider
from mag.settings import Settings

REPO = Path(__file__).resolve().parent.parent
PROCESSED = REPO / "data" / "processed" / "bowes2023"
RUNS = REPO / "data" / "runs" / "jansen_bowes2023"
MAX_IMAGES = 12  # correlation matrices are the priority; cap to control tokens

# The 53 valid construct tokens (gold vocabulary). Used to drop outcomes that are
# not real constructs (e.g. the model occasionally leaks a CTType token "General").
WHITELIST_TOKENS = {
    "Delusion", "Anthro", "BSR", "IOA", "PNR", "Dog", "ConjFall", "NeedClose", "REIR", "NFCog",
    "IntCT", "CRT", "AOT", "BDW", "ExThreat", "Cyn", "Powerlessness", "Anx", "DeathAnx", "Efficacy",
    "Control", "SocThreat", "CollNarc", "Anomie", "Alien", "RWA", "IndNarc", "CollSelfEst", "SDO",
    "NFUnique", "IndSelfEst", "Trust", "Neuro", "Open", "Consc", "Extra", "Agree", "HH", "Anger",
    "Antag", "Depression", "Detach", "Dis", "NegAff", "Paranoia", "PhysAgg", "Psych", "Schizo",
    "UnusExp", "Hostility", "REII", "PercInt", "VerbAgg",
}

# Construct whitelist (token = construct). Same vocabulary as Jansen's Bowes
# prompt; gold uses these exact tokens.
WHITELIST_LINES = (
    "EPISTEMIC: Delusion=Delusion-proneness, Anthro=Anthropomorphism, BSR=Bullshit Receptivity, "
    "IOA=Intolerance of ambiguity, PNR=Perceived non-randomness/illusory pattern perception, "
    "Dog=Dogmatism, ConjFall=Conjunction Fallacy, NeedClose=Need for closure, "
    "REIR=Self-reported rationality, NFCog=Need for Cognition, IntCT=Intelligence, "
    "CRT=Cognitive Reflection, AOT=Actively Open-Minded Thinking\n"
    "EXISTENTIAL: BDW=Belief in a Dangerous World, ExThreat=Existential threat, Cyn=Cynicism, "
    "Powerlessness, Anx=Anxiety, DeathAnx=Death Anxiety, Efficacy, Control\n"
    "SOCIAL: SocThreat=Social threat perception, CollNarc=Collective Narcissism, Anomie, "
    "Alien=Alienation, RWA=Right-wing authoritarianism, IndNarc=Individual narcissism, "
    "CollSelfEst=Collective Self-Esteem, SDO=Social dominance orientation, NFUnique=Need for "
    "Uniqueness, IndSelfEst=Individual self-esteem, Trust\n"
    "PERSONALITY: Neuro=Neuroticism, Open=Openness, Consc=Conscientiousness, Extra=Extraversion, "
    "Agree=Agreeableness, HH=Honesty-Humility\n"
    "PSYCHOPATHOLOGY: Anger, Antag=Antagonism, Depression, Detach=Detachment, Dis=Disinhibition, "
    "NegAff=Negative affect, Paranoia, PhysAgg=Physical Aggression, Psych=Psychoticism, "
    "Schizo=Schizotypy, UnusExp=Susceptibility to unusual experiences, Hostility, "
    "REII=Self-reported intuition, PercInt=Perceived Intentionality, VerbAgg=Verbal Aggression"
)

WIRE_SCHEMA = {
    "type": "object",
    "properties": {
        "conspiracy_measure": {"type": "string"},
        "study": {
            "type": "object",
            "properties": {
                "YearOfPub": {"type": "integer"},
                "CTType": {"type": "array", "items": {"type": "string"}},
                "COVID": {"type": "string"},  # "Yes" | "No"
            },
            "required": ["YearOfPub", "CTType", "COVID"],
        },
        "samples": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "sample_label": {"type": "string"},
                    "N": {"type": "integer"},
                    "female_pct": {"type": "number"},
                    "recruitment": {"type": "string"},  # Student|Com|Mixed|Soldier
                },
                "required": ["sample_label", "N", "female_pct", "recruitment"],
            },
        },
        "effect_sizes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "outcome": {"type": "string"},
                    "es": {"type": "number"},
                    "N": {"type": "integer"},
                    "sample_label": {"type": "string"},
                    "source_construct": {"type": "string"},
                    "evidence": {"type": "string"},
                },
                "required": ["outcome", "es", "N"],
            },
        },
    },
    "required": ["study", "samples", "effect_sizes"],
}

# Our method-tuned prompt. Reads the paper once and emits ALL variables: study,
# samples, and effect sizes. Multimodal table-reading, anchor disambiguation,
# per-sample attribution, scale->token mapping, sign/asterisk handling, evidence.
SYSTEM = f"""You are a meta-analysis coding agent for a review of the CORRELATES
of conspiratorial ideation (belief in conspiracy theories). Read the WHOLE study
once — Marker markdown, the per-table TEXT GRIDS (under "# TABLES"), AND the
attached table/figure IMAGES — and extract every variable below in a single
consistent pass. Cross-check grid vs image: the grid preserves row/column labels;
the image is ground truth for digits. Correlations and demographics also appear
in PROSE — read it, not only tables.

Output four things: `conspiracy_measure`, `study` (paper-level), `samples`
(one per participant sample), and `effect_sizes` (one per correlation). Keep them
MUTUALLY CONSISTENT: every effect_size's `sample_label` must be one of the
`samples` you list, and its N should match that sample's N.

=== STUDY-LEVEL (one per paper) ===
• YearOfPub: publication year (XXXX) from the header/citation/copyright line.
• CTType: type(s) of the conspiracy measure(s) used — a LIST of: "General"
  (generic conspiracist-belief scales, e.g. GCBS/GCB/BCTI/CMQ), "Specific" (real
  named events, e.g. 9/11), "Stereotype" (outgroup-stereotype conspiracies),
  "Scenario" (hypothetical vignette), "Fictitious" (invented non-circulated).
  IMPORTANT: if the study uses BOTH a general measure AND specific/event-based
  items (common — e.g. a GCBS total plus belief in particular theories), emit
  BOTH tokens: ["General", "Specific"]. Use "Mix" ONLY for a SINGLE measure that
  itself blends types and cannot be split. Decide from the conspiracy MEASURE(S),
  not the paper topic. List every distinct type the study's measures cover.
• COVID: "Yes" only if the conspiracy measure's ITEMS are COVID-19/pandemic
  specific; else "No".

=== SAMPLES (one record per participant sample) ===
A "sample" = ONE distinct participant group that has its OWN reported N and its
OWN set of correlations (its own correlation matrix / results). Most papers have
ONE sample (sample_label "main sample"). A paper reporting SEPARATE studies /
experiments / sub-samples gets one record EACH ("Study 1","Study 2","Sample 1"...).

CRITICAL census rules (getting the count and N right matters as much as the values):
  • One record per real participant group. Do NOT split a single sample by gender,
    age, country, or condition unless each part has its OWN separate correlation
    matrix and N.
  • Do NOT invent a "combined/pooled/total" sample that aggregates other samples.
    If the paper reports 3 studies (N=40, 111, 137), emit exactly those three —
    never a 4th row with N=288, and never one merged row.
  • Each sample's N must be a number the paper ACTUALLY reports for THAT group —
    never a sum you computed across studies, and never a grand total.
  • If you cannot find a separate N + separate correlations for a candidate group,
    do not emit it as its own sample.

For each sample:
• N: that sample's own reported overall size (per the rules above).
• female_pct: PERCENT female of THAT sample (0-100). If a count is given,
  convert female_pct = n_female / N * 100; if only n_male, (N-n_male)/N*100;
  all-female=100, all-male=0. Report a PERCENT, never the raw count.
• recruitment: one of "Student" (university/college), "Com" (community / general
  public / online panel e.g. MTurk/Prolific), "Mixed" (a single sample combining
  sources), "Soldier" (military/veterans).

=== EFFECT SIZES (one per correlation) ===
Extract every zero-order correlation (Pearson r / Spearman rho) between the
study's conspiratorial-ideation measure and any whitelisted construct.

>>> RECALL IS THE TOP PRIORITY. Missing a correlation is the WORST error. It is
>>> FINE — encouraged — to extract MORE comprehensively than strictly needed
>>> (e.g. a construct's total AND its subscales, the construct against several
>>> conspiracy measures). Never omit a correlation to avoid a duplicate or to be
>>> conservative. When in doubt, INCLUDE it. If a correlation matrix exists, you
>>> must return a non-empty list.

STEP 1 — FIND EVERY CORRELATION SOURCE. Conspiracy correlations live in three
places — check ALL of them, do not stop early:
  (a) a zero-order CORRELATION MATRIX (the main source), often a triangular table
      with a 1.00 / α-reliability diagonal and all cells in [-1, 1];
  (b) the RESULTS PROSE ("conspiracy beliefs correlated .31 with paranoia");
  (c) a validation/supplementary table where the conspiracy scale is one row
      among many (common when conspiracy is a secondary measure).
  CRITICAL — COMPOSITE IMAGES: a single attached image OFTEN contains MORE THAN
  ONE element — e.g. a chart/scatterplot in the TOP half AND a separate DATA TABLE
  (such as the correlation matrix) in the BOTTOM half of the SAME image. Marker
  frequently merges a figure and an adjacent table into one image, or saves a
  correlation matrix as a "figure". Therefore:
    • Treat EVERY attached image (table AND figure) as possibly containing a data
      table. Scan the ENTIRE image top-to-bottom; do not stop at a chart.
    • If an image shows a chart on top, KEEP LOOKING below it for a table of
      numbers — the correlation matrix is often printed right under a plot.
    • A "Figure" caption on top does not mean there is no table lower down; read
      any "Table N: Correlation matrix..." caption and grid wherever it appears.
  The correlation matrix is frequently present ONLY as such an image and NOT in
  the "# TABLES" text grids (Marker fails to parse it). INSPECT EVERY ATTACHED
  IMAGE in full. If the prose says "correlations are shown in Table N", find that
  matrix among the images and read it. Do NOT conclude "no correlations" just
  because the text grids only contain regression or
  descriptive tables.
  DO NOT extract from REGRESSION tables (columns B, SE, β / beta, t, Wald, p,
  OR / Exp(B)) — a regression coefficient is NOT a zero-order correlation. Use
  only the bivariate r.

STEP 2 — IDENTIFY THE ANCHOR. The conspiracy measure: GCBS/GCB ("Generic
Conspiracist Beliefs"), CMQ ("Conspiracy Mentality"), BCTI, CMS, "conspiracy
beliefs/ideation", or a TOPIC-SPECIFIC conspiracy scale (HIV / COVID / vaccine /
9-11 conspiracy beliefs). Report it in `conspiracy_measure`. Every correlation
must be BETWEEN this anchor and a whitelisted construct. If several conspiracy
measures appear (e.g. BCTI, CMQ, GCBS subscales + GCBS total), prefer the
general/total column; you MAY also report the construct against the other
conspiracy measures rather than miss data — duplicates are acceptable, omissions
are not. Never pair two conspiracy measures with each other.
  ORIENTATION: the conspiracy measure may be a ROW or a COLUMN, and a paper may
  list SEVERAL conspiracy sub-measures (e.g. "general / classical / political /
  interpersonal conspiracy theories") with the whitelisted CONSTRUCT as the other
  axis. Extract every conspiracy-measure × whitelisted-construct cell regardless
  of which axis the construct is on. If the construct (e.g. "subjective
  randomness") is a single row/column and the conspiracy measures are the others,
  read that construct's cell against EACH conspiracy measure.

STEP 3 — READ THE MATRIX CELL-BY-CELL. Locate the anchor's ROW or COLUMN and walk
EVERY cell; for each cell whose other variable maps to a whitelist token, record
the r:
  • Keep the SIGN. ".27" is positive; "-.27"/"−.27" is negative; honor prose like
    "a negative correlation".
  • Strip significance markers (*, **, ***, †, superscripts) — keep only the
    number. Values may have 2-3 decimals (e.g. -.002); never report |r|>1.
  • Do NOT read the diagonal (1.00 / α reliabilities) or M/SD/Mean columns as r.
  • Watch OCR slips in the image (O vs 0, l/I vs 1, comma vs dot); trust the image
    digits and cross-check the text grid.

N RULE — for EACH effect_size, set `N` to the OVERALL N of its sample (the SAME
value you report in `samples[].N`), NOT a per-correlation / listwise / pairwise n
from a table footnote. Every correlation from one sample shares that sample's N.

STEP 4 — MAP CONSTRUCT -> TOKEN (case-sensitive, EXACT whitelist token):
  • Big Five / NEO / BFI / HEXACO subscales -> Neuro, Extra, Open, Agree, Consc
    (+ HH for HEXACO honesty-humility).
  • SPQ / SPQ-B / O-LIFE / schizotypy -> Schizo;  paranoia scale -> Paranoia.
  • "REI analytical-rational" / "rational thinking" -> REIR;  "REI
    intuitive-experiential" / "faith in intuition" -> REII.
  • DWS / "dangerous world" -> BDW;  powerlessness / "lack of control" -> Powerlessness;
    "need for cognition" -> NFCog;  CRT -> CRT;  bullshit receptivity -> BSR;
    illusory pattern perception / perceived non-randomness / "subjective
    randomness" / "perception of randomness" / "prior for randomness" -> PNR;
    magical / superstitious / unusual-experience beliefs -> UnusExp;  RWA -> RWA;
    SDO -> SDO;  intolerance of ambiguity -> IOA;  need for (cognitive) closure /
    NFCC -> NeedClose;  interpersonal trust / trust in others -> Trust;
    cynicism -> Cyn;  anomie -> Anomie;  alienation -> Alien.
  • PREFER the construct's TOTAL/composite. If subscales are ALSO reported, you may
    include them too (recall first) — but always include the total when present.
  • Skip a column/row only when it maps to NO token (e.g. Education, age, political
    orientation, the conspiracy measures themselves).

  CONSTRUCT DIRECTION (SIGN) — each whitelist token names a construct with a
  DEFINED conceptual direction; report `es` with the sign that matches the TOKEN's
  direction. If the paper measures the OPPOSITE pole of that construct, the
  reported r is in the reverse direction, so FLIP its sign (negate) so the value
  expresses the token's construct. Only flip when the measured variable is clearly
  the reverse pole; otherwise copy the printed sign as-is. Examples:
    - Trust: a "mistrust" / "cultural mistrust" / "medical mistrust" measure is the
      reverse of trust -> negate (printed mistrust r = .48 -> Trust es = -0.48).
    - ConjFall (conjunction FALLACY / susceptibility): a measure of "conjunction
      accuracy" / "correct conjunction responses" / resistance to the fallacy is
      the reverse -> negate (printed accuracy r = -.22 -> ConjFall es = +0.22).
    - PNR (illusory pattern / seeing non-randomness): a measure of "accuracy at
      detecting randomness" / correct randomness judgments is the reverse -> negate.
    - CRT / cognitive-reflection ACCURACY is itself the token direction (do NOT
      flip) — only flip when the variable is explicitly the construct's opposite.

STEP 4 — N AND SAMPLE. Report `N` = the overall sample size the correlation is
based on (mind pairwise-deletion / per-correlation n footnotes; use the
table/sample N). If the paper reports SEPARATE samples/studies (each with its own
matrix and N), attribute each correlation to its sample via `sample_label`
("main sample", "Study 1", "Study 2", "Sample 1"...) and use that sample's N.

Each effect_size: `outcome` (a CONSTRUCT token from the whitelist below — NEVER a
CTType label like "General"/"Specific"; those are not constructs), `es` (exact,
signed), `N`, `sample_label` (one of the samples above), `source_construct`
(construct name as printed), `evidence` (the cell/sentence read, short verbatim).
Bivariate zero-order only — ignore partial/adjusted r, betas, interactions,
composites of multiple constructs, factor loadings, path coefficients. Do NOT
invent or emit a placeholder value: if you cannot actually read a correlation's
number (e.g. it is only in an online supplement not shown here), OMIT that
correlation — never report es=0 as a stand-in. Empty list if none.

WHITELIST (token = construct):
{WHITELIST_LINES}
"""


def _iter_blocks(node: dict):
    yield node
    for c in node.get("children") or []:
        yield from _iter_blocks(c)


def _html_table_to_grid(html: str) -> str:
    """Convert a Marker <table> HTML to a pipe-delimited text grid (rows/cols
    preserved). build_sections drops Table blocks, so we add them back as text
    alongside the table images — the model gets BOTH modalities."""
    rows: list[str] = []
    for tr in re.findall(r"<tr>(.*?)</tr>", html, flags=re.S | re.I):
        cells = re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", tr, flags=re.S | re.I)
        cells = [re.sub(r"<[^>]+>", " ", c).strip() for c in cells]
        cells = [re.sub(r"\s+", " ", c) for c in cells]
        if any(cells):
            rows.append(" | ".join(cells))
    return "\n".join(rows)


def tables_as_text(paper_dir: Path, paper_id: str) -> str:
    """Pipe-grid text for every JSON Table block that looks like a data table."""
    doc = json.loads((paper_dir / f"{paper_id}.json").read_text(encoding="utf-8"))
    out: list[str] = []
    n = 0
    for blk in _iter_blocks(doc):
        if blk.get("block_type") != "Table":
            continue
        html = blk.get("html") or ""
        # keep only tables that carry decimals (correlation/descriptive matrices)
        if len(re.findall(r"-?\.\d", html)) < 4:
            continue
        grid = _html_table_to_grid(html)
        if grid:
            n += 1
            out.append(f"[TABLE {n} — {blk.get('id', '')}]\n{grid}")
    return "\n\n".join(out)


def collect(paper_dir: Path, paper_id: str) -> tuple[str, list[WireAsset]]:
    normalize_manifests(paper_dir)  # rebase Fir-absolute image paths -> local (idempotent)
    sections = build_sections(paper_dir, paper_id)
    prose = "\n\n".join(f"## {s.section_title or s.section_id}\n{s.text}".strip() for s in sections)
    tbl_text = tables_as_text(paper_dir, paper_id)
    text = prose
    if tbl_text:
        text += "\n\n# TABLES (text grids — cross-check against the attached table images)\n\n" + tbl_text
    # Load images DIRECTLY from the tables/ and figures/ dirs. We do NOT rely on
    # build_sections asset attachment: the figures manifest schema (file/page/index)
    # doesn't match what _attach_asset expects (image_path/page_index), so figure
    # images — where Marker often saves correlation matrices (e.g. Ball2017) — would
    # otherwise never be fed. Tables first (correlation matrices), then figures.
    img_paths = sorted((paper_dir / "tables").glob("*.png")) + \
        sorted((paper_dir / "figures").glob("*.png"))
    wire: list[WireAsset] = []
    for p in img_paths[:MAX_IMAGES]:
        try:
            data = p.read_bytes()
        except OSError:
            continue
        wire.append(WireAsset(path=str(p), mime_type="image/png", data=data))
    return text, wire


def run_one(paper_dir: Path, paper_id: str, provider: GeminiProvider, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    final = out_dir / "extraction.json"
    if final.exists() and final.stat().st_size > 40:
        return {"paper_id": paper_id, "status": "skipped"}
    text, assets = collect(paper_dir, paper_id)
    user = (
        f"PAPER: {paper_id}\n\n{text}\n\n"
        f"[{len(assets)} table/figure image(s) attached — read cell values from "
        f"the images.]\n\nExtract study, samples, and all effect sizes now."
    )
    resp = provider._generate(
        wire_schema=WIRE_SCHEMA, system_prompt=SYSTEM, user_prompt=user, assets=assets
    )
    d = resp.data if isinstance(resp.data, dict) else {}
    es = d.get("effect_sizes", []) or []
    samples = d.get("samples", []) or []

    # CONDITIONAL N alignment: gold usually uses a sample's OVERALL N for all its
    # effect sizes, while the model sometimes copies a per-correlation/listwise n.
    # Overwrite ES N with the matched sample's N ONLY when they are close (a
    # listwise-vs-total gap, <=15%) or the paper has a single sample. If a paper
    # genuinely reports several different Ns (multi-wave, e.g. ArdevolAbreu
    # 3073/5428), trust the ES's own N rather than force one value. Keep the
    # model's original as N_reported for audit.
    by_label = {s.get("sample_label"): s.get("N") for s in samples if s.get("N") is not None}
    sole_n = next(iter(by_label.values())) if len(by_label) == 1 else None
    for r in es:
        sn = by_label.get(r.get("sample_label"), sole_n)
        rn = r.get("N")
        if sn is None or rn == sn:
            continue
        try:
            close = rn is not None and abs(float(rn) - float(sn)) <= 0.15 * float(sn)
        except (TypeError, ValueError):
            close = False
        # Only snap to the sample N for the listwise-vs-total case (close) or when
        # the model gave no N. A large gap signals a genuinely different N (multi-
        # wave) — leave it alone rather than corrupt it.
        if rn is None or close:
            r["N_reported"] = rn
            r["N"] = sn

    # Drop rows whose outcome is not a real construct token (e.g. a leaked CTType
    # token like "General"). Keeps the effect_sizes clean without touching recall
    # of true constructs.
    dropped = [r for r in es if r.get("outcome") not in WHITELIST_TOKENS]
    es = [r for r in es if r.get("outcome") in WHITELIST_TOKENS]
    d["effect_sizes"] = es
    payload = {
        "conspiracy_measure": d.get("conspiracy_measure"),
        "study": d.get("study", {}),
        "samples": samples,
        "effect_sizes": es,
        "_meta": {
            "paper_id": paper_id, "n_samples": len(samples), "n_effect_sizes": len(es),
            "n_images": len(assets), "prompt_tokens": resp.prompt_tokens,
            "completion_tokens": resp.completion_tokens,
        },
    }
    final.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    return {"paper_id": paper_id, "status": "ok", "n_es": len(es),
            "n_samp": len(samples), "n_img": len(assets)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", nargs="*", help="restrict to these paper ids")
    ap.add_argument("--processed", type=Path, default=PROCESSED)
    args = ap.parse_args()

    if not args.processed.is_dir():
        sys.exit(f"!! marker dir not found: {args.processed} (run Marker first)")
    papers = sorted(
        d for d in args.processed.iterdir() if d.is_dir() and (d / f"{d.name}.json").exists()
    )
    if args.only:
        papers = [d for d in papers if d.name in args.only]
    if not papers:
        sys.exit("!! no Marker-processed papers found")

    provider = GeminiProvider.from_settings(Settings())
    print(f"Unified Bowes extraction (study + samples + effect sizes) over {len(papers)} papers\n")
    for i, pdir in enumerate(papers, 1):
        try:
            r = run_one(pdir, pdir.name, provider, RUNS / pdir.name)
            tag = (f"{r['n_samp']} samples, {r['n_es']} ES, {r['n_img']} img"
                   if r["status"] == "ok" else r["status"])
            print(f"[{i}/{len(papers)}] {pdir.name:18s} {tag}")
        except Exception as exc:  # noqa: BLE001
            print(f"[{i}/{len(papers)}] {pdir.name:18s} ERROR: {type(exc).__name__}: {exc}"[:160])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
