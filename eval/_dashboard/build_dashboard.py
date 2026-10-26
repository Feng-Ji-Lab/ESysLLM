"""Build a self-contained reference-vs-extracted dashboard for Vu / Ng.

A ``paper x field`` matrix: each cell shows the value our v2 (``mag``) pipeline
extracted; the cell background encodes the match against the authors' own coding;
hover or click a cell to see the reference value, the gold source, and the
supporting evidence (quote + section + page) pulled from ``paper_rich.json``.

The page also shows, collapsibly at the top, the customizable assets for each
meta-analysis (prompts, schema/field definitions, rules, ground-truth mapping),
and two metric panels following the revision paper's measurement standard
(CED / IED / MD -> precision, recall, F1, accuracy) under two standards:

  Strict   - a field counts as correct only on an exact match.
  Widened  - a field also counts as correct when the reference value(s) appear
             within the extraction (extras allowed) -- the paper's "partial match".

This mirrors the v1 ESysLLM dashboard (github_v1/validation/build_dashboard.py)
but feeds from v2 run outputs and the gold logic in goldlib_vu / goldlib_ng.

Usage:
    conda activate research
    python -m eval._dashboard.build_dashboard --ma vu --out docs/reports/2026-06-14-vu-eval-dashboard.html
    python -m eval._dashboard.build_dashboard --ma ng --out docs/reports/2026-06-14-ng-eval-dashboard.html
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import goldlib_bennett, goldlib_bowes, goldlib_buecker, goldlib_ng, goldlib_vu
from .common import GoldNotAvailable

REPO = Path(__file__).resolve().parents[2]
MODULES = {
    "vu": goldlib_vu,
    "ng": goldlib_ng,
    "bennett": goldlib_bennett,
    "buecker": goldlib_buecker,
    "bowes": goldlib_bowes,
}


def _is_none_like(v) -> bool:
    if v is None:
        return True
    return str(v).strip().lower() in {"none", "nan", "", "."}


def _render_value(raw):
    """Turn a paper_target field value into a structured cell payload.

    Returns one of:
      {"kind": "scalar", "text": "..."}
      {"kind": "cells", "rows": [[label, ["v1", "v2"]], ...]}
      {"kind": "empty"}
    """
    if isinstance(raw, dict):
        rows = []
        for label, cell in raw.items():
            vals = cell if isinstance(cell, list) else [cell]
            vals = [str(v) for v in vals if not _is_none_like(v)]
            rows.append([label, vals])
        rows = [r for r in rows if r[1]]
        return {"kind": "cells", "rows": rows} if rows else {"kind": "empty"}
    if isinstance(raw, list):
        vals = [str(v) for v in raw if not _is_none_like(v)]
        return {"kind": "scalar", "text": ", ".join(vals)} if vals else {"kind": "empty"}
    if _is_none_like(raw):
        return {"kind": "empty"}
    return {"kind": "scalar", "text": str(raw)}


def _collect_evidence(rich: dict | None, field: str, limit: int = 6) -> list[dict]:
    """Gather evidence snippets for a field from paper_rich.json."""
    if not rich:
        return []
    fobj = (rich.get("fields") or {}).get(field)
    if not isinstance(fobj, dict):
        return []
    snippets: list[dict] = []

    def take(ev_list, sample=None):
        for ev in ev_list or []:
            quote = (ev.get("quote") or "").strip()
            if not quote:
                continue
            snippets.append(
                {
                    "sample": sample,
                    "section": ev.get("section_title") or ev.get("section_id") or "",
                    "page": ev.get("page"),
                    "quote": quote[:400],
                }
            )

    pv = fobj.get("paper_value")
    if isinstance(pv, dict):
        take(pv.get("evidence"))
    cells = fobj.get("cells")
    if isinstance(cells, dict):
        for sample_key, cell in cells.items():
            if isinstance(cell, dict):
                for valobj in cell.get("values", []) or []:
                    if isinstance(valobj, dict):
                        take(valobj.get("evidence"), sample=sample_key)
    return snippets[:limit]


def _ordered_fields(papers: list[dict], evaluated: tuple[str, ...]) -> list[str]:
    seen: set[str] = set()
    for p in papers:
        seen.update(p["_target"].keys())
    extras = sorted(f for f in seen if f not in evaluated)
    return [f for f in evaluated if f in seen] + extras


# --- metrics (revision paper's CED / IED / MD framework) --------------------


def _metrics(ced: int, ied: int, md: int) -> dict:
    scored = ced + ied + md
    p = ced / (ced + ied) if (ced + ied) else 0.0
    r = ced / (ced + md) if (ced + md) else 0.0
    f1 = 2 * p * r / (p + r) if (p + r) else 0.0
    acc = ced / scored if scored else 0.0
    return {
        "ced": ced,
        "ied": ied,
        "md": md,
        "precision": p,
        "recall": r,
        "f1": f1,
        "accuracy": acc,
    }


def _from_counts(c: dict, standard: str) -> dict:
    if standard == "strict":
        return _metrics(c["exact"], c["contains"] + c["wrong"], c["missing"])
    return _metrics(c["exact"] + c["contains"], c["wrong"], c["missing"])  # widened


def _summarize(counts: dict, fields: tuple[str, ...]) -> dict:
    per_field = {}
    tot = {"exact": 0, "contains": 0, "wrong": 0, "missing": 0}
    for f in fields:
        c = counts[f]
        for k in tot:
            tot[k] += c[k]
        per_field[f] = {
            "counts": c,
            "strict": _from_counts(c, "strict"),
            "widened": _from_counts(c, "widened"),
        }
    return {
        "per_field": per_field,
        "overall": {
            "counts": tot,
            "strict": _from_counts(tot, "strict"),
            "widened": _from_counts(tot, "widened"),
        },
    }


# --- customizable assets (prompts / schema / rules / mapping) ----------------


def _collect_assets(mod) -> list[dict]:
    assets: list[dict] = []

    def add(group: str, path: Path):
        if path.exists() and path.is_file():
            try:
                rel = str(path.relative_to(REPO))
            except ValueError:
                rel = str(path)
            assets.append({"group": group, "title": rel, "text": path.read_text(encoding="utf-8")})

    # A module may name its own asset files (Bowes: the prompt lives in the extractor
    # script, not in prompts.yaml); otherwise show the bundle's prompts + fields.
    for group, path in getattr(mod, "ASSET_FILES", None) or (
        ("Prompts", mod.SCHEMA_DIR / "prompts.yaml"),
        ("Schema & field definitions", mod.SCHEMA_DIR / "fields.json"),
    ):
        add(group, path)

    rules_dir = REPO / "rules"
    seen: set[str] = set()
    for pat in mod.RULE_GLOBS:
        for d in sorted(rules_dir.glob(pat)):
            if not d.is_dir() or d.name in seen:
                continue
            seen.add(d.name)
            for f in sorted(d.iterdir()):
                if f.suffix.lower() in (".md", ".yaml", ".yml"):
                    add("Rules", f)

    add("Ground-truth mapping", mod.EVAL_MAP)
    return assets


def build(ma: str, runs_dir: Path | None = None) -> dict:
    """Assemble the dashboard data model for one meta-analysis."""
    mod = MODULES[ma]
    runs = runs_dir or mod.RUNS
    # RUNS may be one dir or several (Bennett's three batches); a module may also
    # name a different per-paper file and supply its own loader (Bowes' extraction.json).
    run_dirs = list(runs) if isinstance(runs, (list, tuple)) else [runs]
    paper_file = getattr(mod, "PAPER_FILE", "paper_target.json")
    loader = getattr(mod, "load_target", None)
    paper_dirs = sorted(
        (d for r in run_dirs if r.exists() for d in r.iterdir()
         if d.is_dir() and (d / paper_file).exists()),
        key=lambda d: d.name,
    )

    raw_papers = []
    for d in paper_dirs:
        if loader is not None:
            loaded = loader(d)
            if loaded is None:
                continue
            target, rich = loaded
        else:
            target = json.loads((d / paper_file).read_text())
            rich_path = d / "paper_rich.json"
            rich = json.loads(rich_path.read_text()) if rich_path.exists() else None
        raw_papers.append({"id": d.name, "_target": target, "_rich": rich})

    fields = _ordered_fields(raw_papers, mod.EVALUATED_FIELDS)

    counts = {
        f: {"exact": 0, "contains": 0, "wrong": 0, "missing": 0} for f in mod.EVALUATED_FIELDS
    }
    papers_out = []
    for rp in raw_papers:
        cells = {}
        for field in fields:
            payload = _render_value(rp["_target"].get(field))
            try:
                ev = mod.evaluate(rp["id"], field, rp["_target"])
                klass, gold, gold_source = ev.klass, ev.gold_display, ev.gold_source
            except GoldNotAvailable:
                klass, gold, gold_source = "neutral", None, None
            if field in counts and klass != "neutral":
                counts[field][klass] += 1
            payload.update(
                {
                    "klass": klass,
                    "gold": gold,
                    "gold_source": gold_source,
                    "evidence": _collect_evidence(rp["_rich"], field),
                }
            )
            cells[field] = payload
        papers_out.append({"id": rp["id"], "cells": cells})

    return {
        "ma_name": mod.MA_NAME,
        "gold_label": mod.GOLD_LABEL,
        "evaluated_fields": list(mod.EVALUATED_FIELDS),
        "fields": fields,
        "papers": papers_out,
        "summary": _summarize(counts, mod.EVALUATED_FIELDS),
        "assets": _collect_assets(mod),
    }


def render_html(data: dict) -> str:
    blob = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")  # safe inside <script>
    return HTML_TEMPLATE.replace("/* __DATA__ */", blob)


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Eval Dashboard — reference vs extracted</title>
<style>
:root {
  --bg:#f8f9fa; --text:#212529; --border:#dee2e6;
  --header-bg:#343a40; --header-text:#f8f9fa;
  --cell-border:rgba(150,150,150,0.4);
  --full:rgba(72,199,116,0.28); --partial:rgba(255,221,87,0.34);
  --none:rgba(255,99,99,0.24); --neutral:rgba(200,200,200,0.12);
  --full-s:#48c774; --partial-s:#ffdd57; --none-s:#ff6363; --neutral-s:#ccc;
}
* { box-sizing:border-box; margin:0; padding:0; }
body { font-family:'Segoe UI',system-ui,-apple-system,sans-serif; font-size:13px; background:var(--bg); color:var(--text); line-height:1.4; }
.topbar { background:#fff; border-bottom:2px solid var(--border); padding:12px 18px; }
.topbar h1 { font-size:1.2rem; font-weight:700; }
.topbar .sub { color:#6b7280; font-size:12px; margin-top:2px; }

/* assets */
.assets { margin:12px 0; border:1px solid var(--border); border-radius:8px; background:#fcfcfd; }
.assets > summary { cursor:pointer; padding:10px 14px; font-weight:600; color:#1d4ed8; list-style:none; }
.assets > summary::before { content:'▸ '; }
.assets[open] > summary::before { content:'▾ '; }
.assets-body { padding:6px 14px 14px; }
.asset-group { margin-top:10px; }
.asset-group > .gh { font-weight:700; font-size:12px; color:#374151; text-transform:uppercase; letter-spacing:.04em; margin:8px 0 4px; }
.asset details { border:1px solid var(--border); border-radius:6px; margin:5px 0; background:#fff; }
.asset details > summary { cursor:pointer; padding:6px 10px; font-family:ui-monospace,Menlo,Consolas,monospace; font-size:12px; color:#0f172a; }
.asset pre { margin:0; padding:10px 12px; border-top:1px solid var(--border); background:#0f172a; color:#e2e8f0; font-size:11.5px; line-height:1.5; overflow:auto; max-height:420px; }

/* standard toggle + metric panels */
.stdtoggle { margin:12px 0 6px; display:flex; gap:18px; align-items:center; font-size:13px; }
.stdtoggle label { cursor:pointer; }
.stdtoggle .hint { color:#6b7280; font-size:12px; }
.panels { display:grid; grid-template-columns:1fr 1fr; gap:14px; }
@media (max-width:900px){ .panels { grid-template-columns:1fr; } }
.panel { border:1px solid var(--border); border-radius:10px; padding:12px 14px; background:#fff; }
.panel.active { border-color:#1d4ed8; box-shadow:0 0 0 2px rgba(29,78,216,.12); }
.panel h3 { font-size:13px; margin-bottom:8px; }
.panel h3 .tag { font-weight:500; color:#6b7280; }
.bigrow { display:flex; gap:16px; margin:6px 0 8px; }
.big b { font-size:1.45rem; font-weight:700; display:block; line-height:1; }
.big span { font-size:11px; color:#6b7280; }
.counts { font-size:11.5px; color:#6b7280; margin-bottom:8px; }
table.fm { width:100%; border-collapse:collapse; font-size:11.5px; }
table.fm th, table.fm td { padding:3px 6px; border-bottom:1px solid var(--border); text-align:right; }
table.fm th:first-child, table.fm td:first-child { text-align:left; }
table.fm th { color:#6b7280; font-weight:600; }

/* controls */
.controls { position:sticky; top:0; z-index:1000; background:#fff; border-bottom:2px solid var(--border); padding:8px 16px; display:flex; flex-wrap:wrap; gap:10px; align-items:center; }
.controls label { font-weight:600; font-size:12px; }
.controls input[type=text], .controls select { padding:4px 8px; border:1px solid var(--border); border-radius:4px; font-size:12px; }
.controls input[type=text] { width:200px; }
.controls .sep { border-left:1px solid var(--border); height:26px; }
.controls .badge { background:#e9ecef; padding:2px 8px; border-radius:10px; font-size:11px; color:#495057; }
.legend { display:flex; gap:12px; align-items:center; font-size:11px; flex-wrap:wrap; }
.legend-item { display:flex; align-items:center; gap:4px; }
.legend-swatch { width:14px; height:14px; border-radius:3px; border:1px solid rgba(0,0,0,0.15); }

/* table */
.table-wrap { overflow:auto; max-height:calc(100vh - 60px); }
table.grid { border-collapse:separate; border-spacing:0; min-width:100%; }
.grid thead th { position:sticky; top:0; z-index:100; background:var(--header-bg); color:var(--header-text); padding:8px 10px; font-size:11px; font-weight:600; text-align:left; white-space:nowrap; border-right:1px solid rgba(255,255,255,0.1); min-width:150px; }
.grid thead th.evald::after { content:" \2605"; color:#ffd43b; }
.grid thead th:first-child { left:0; z-index:200; min-width:170px; max-width:220px; }
.grid tbody td { vertical-align:top; padding:4px 6px; border-bottom:1px solid var(--border); border-right:1px solid var(--border); min-width:150px; }
.grid tbody td:first-child { position:sticky; left:0; z-index:50; background:#fff; font-weight:600; font-size:12px; min-width:170px; max-width:220px; word-break:break-word; border-right:2px solid var(--border); }
.cell { border:1px solid var(--cell-border); border-radius:4px; padding:4px 6px; cursor:pointer; min-height:24px; transition:box-shadow .15s; }
.cell:hover { box-shadow:0 0 0 2px rgba(66,133,244,0.3); }
.cell.pinned { box-shadow:0 0 0 2px rgba(66,133,244,0.6); }
.cell.full { background:var(--full); } .cell.partial { background:var(--partial); }
.cell.none { background:var(--none); } .cell.neutral { background:var(--neutral); }
.sub { margin-bottom:3px; } .sub:last-child { margin-bottom:0; }
.sub-h { font-weight:600; font-size:11px; color:#495057; }
.empty-val { color:#aaa; font-style:italic; }
.tooltip { position:fixed; z-index:5000; background:#fff; border:1px solid #aaa; border-radius:6px; padding:10px 12px; max-width:520px; min-width:220px; box-shadow:0 4px 16px rgba(0,0,0,.18); font-size:12px; line-height:1.5; display:none; }
.tooltip.pinned { pointer-events:auto; }
.tt-row { margin-bottom:5px; } .tt-label { font-weight:700; color:#333; }
.tt-klass { display:inline-block; padding:1px 8px; border-radius:999px; font-weight:700; font-size:11px; background:#eef; }
.tt-std { font-size:11px; color:#374151; }
.tt-gold { border-top:1px dashed #ccc; padding-top:6px; margin-top:6px; }
.tt-src { color:#6b7280; font-size:11px; }
.tt-ev { border-top:1px dashed #ccc; padding-top:6px; margin-top:6px; }
.tt-ev .q { color:#333; } .tt-ev .meta { color:#6b7280; font-size:11px; }
</style>
</head>
<body>
<div class="topbar">
  <h1 id="title"></h1>
  <div class="sub" id="subtitle"></div>

  <details class="assets" id="assetsPanel">
    <summary>Customizations — prompts · schema · field definitions · rules (click to expand)</summary>
    <div class="assets-body" id="assetsBody"></div>
  </details>

  <div class="stdtoggle">
    <strong>Standard:</strong>
    <label><input type="radio" name="std" value="strict" checked> Strict (exact match)</label>
    <label><input type="radio" name="std" value="widened"> Widened (reference within extraction)</label>
    <span class="hint">— toggles cell coloring; both panels below always shown</span>
  </div>
  <div class="panels">
    <div class="panel" id="panelStrict"></div>
    <div class="panel" id="panelWidened"></div>
  </div>
</div>

<div class="controls">
  <label>View:</label>
  <select id="viewMode"><option value="all">All papers</option><option value="single">Single paper</option></select>
  <select id="paperSelect" style="display:none"></select>
  <div class="sep"></div>
  <label>Search:</label><input type="text" id="searchBox" placeholder="Filter papers...">
  <div class="sep"></div>
  <div class="legend">
    <div class="legend-item"><div class="legend-swatch" style="background:var(--full)"></div>exact (correct)</div>
    <div class="legend-item"><div class="legend-swatch" style="background:var(--partial)"></div>contains (→correct if widened)</div>
    <div class="legend-item"><div class="legend-swatch" style="background:var(--none)"></div>wrong / missing</div>
    <div class="legend-item"><div class="legend-swatch" style="background:var(--neutral)"></div>no gold</div>
  </div>
  <div class="sep"></div>
  <span class="badge" id="paperCount"></span>
</div>

<div class="table-wrap"><table class="grid"><thead><tr id="headerRow"></tr></thead><tbody id="tableBody"></tbody></table></div>
<div class="tooltip" id="tooltip"></div>

<script>
const DATA = /* __DATA__ */;
const fields = DATA.fields;
const evald = new Set(DATA.evaluated_fields);
const papers = DATA.papers;
const byId = {}; papers.forEach(p => byId[p.id] = p);
let pinned = null;
let std = 'strict';

// klass -> outcome under each standard
const STD = {
  strict:  {exact:'correct', contains:'incorrect (partial)', wrong:'incorrect', missing:'missing'},
  widened: {exact:'correct', contains:'correct',             wrong:'incorrect', missing:'missing'},
};

function esc(s){ const d=document.createElement('div'); d.textContent = s==null?'':String(s); return d.innerHTML; }
function pct(x){ return (x*100).toFixed(1)+'%'; }
function f3(x){ return x.toFixed(3); }

document.getElementById('title').textContent = DATA.ma_name + " — reference vs extracted";
document.getElementById('subtitle').textContent =
  "Gold: " + DATA.gold_label + " · " + papers.length + " papers · ★ = scored field · metric = revision paper CED/IED/MD";

// ---- assets panel ----
(function(){
  const groups = {};
  (DATA.assets||[]).forEach(a => { (groups[a.group] = groups[a.group] || []).push(a); });
  const order = ["Prompts","Schema & field definitions","Rules","Ground-truth mapping"];
  const body = document.getElementById('assetsBody');
  let html = '';
  for (const g of order) {
    const items = groups[g]; if (!items) continue;
    html += `<div class="asset-group"><div class="gh">${esc(g)}</div>`;
    for (const a of items) {
      html += `<div class="asset"><details><summary>${esc(a.title)}</summary><pre>${esc(a.text)}</pre></details></div>`;
    }
    html += `</div>`;
  }
  body.innerHTML = html || '<em>No assets found.</em>';
})();

// ---- metric panels ----
function renderPanel(elId, label, sub){
  const el = document.getElementById(elId);
  const key = elId === 'panelStrict' ? 'strict' : 'widened';
  const o = DATA.summary.overall[key];
  let h = `<h3>${label} <span class="tag">— ${sub}</span></h3>`;
  h += `<div class="bigrow">
    <div class="big"><b>${f3(o.f1)}</b><span>F1</span></div>
    <div class="big"><b>${f3(o.precision)}</b><span>Precision</span></div>
    <div class="big"><b>${f3(o.recall)}</b><span>Recall</span></div>
    <div class="big"><b>${pct(o.accuracy)}</b><span>Accuracy</span></div>
  </div>`;
  h += `<div class="counts">CED ${o.ced} · IED ${o.ied} · MD ${o.md} &nbsp;(${o.ced+o.ied+o.md} scored data points)</div>`;
  h += `<table class="fm"><thead><tr><th>field</th><th>P</th><th>R</th><th>F1</th><th>Acc</th></tr></thead><tbody>`;
  for (const f of DATA.evaluated_fields) {
    const m = DATA.summary.per_field[f][key];
    h += `<tr><td>${esc(f)}</td><td>${f3(m.precision)}</td><td>${f3(m.recall)}</td><td>${f3(m.f1)}</td><td>${pct(m.accuracy)}</td></tr>`;
  }
  h += `</tbody></table>`;
  el.innerHTML = h;
}
renderPanel('panelStrict', 'Strict', 'exact match only');
renderPanel('panelWidened', 'Widened', 'reference within extraction = match');

function markActivePanel(){
  document.getElementById('panelStrict').classList.toggle('active', std==='strict');
  document.getElementById('panelWidened').classList.toggle('active', std==='widened');
}

// ---- cell color ----
function cellColor(klass){
  if (!klass || klass==='neutral') return 'neutral';
  if (klass==='exact') return 'full';
  if (klass==='contains') return std==='widened' ? 'full' : 'partial';
  return 'none'; // wrong | missing
}

function renderCell(cell){
  if (!cell || cell.kind === 'empty') return '<span class="empty-val">(empty)</span>';
  if (cell.kind === 'scalar') return esc(cell.text);
  return cell.rows.map(([label, vals]) =>
    `<div class="sub"><span class="sub-h">${esc(label)}:</span> ${vals.map(esc).join(', ')}</div>`).join('');
}

// ---- tooltip ----
const tt = document.getElementById('tooltip');
function showTip(pid, field, x, y){
  const cell = byId[pid].cells[field];
  if (!cell) { tt.style.display='none'; return; }
  const k = cell.klass || 'neutral';
  let h = `<div class="tt-row"><span class="tt-label">${esc(pid)}</span> · ${esc(field)} <span class="tt-klass">${k}</span></div>`;
  if (k !== 'neutral') {
    h += `<div class="tt-std">strict: <b>${STD.strict[k]}</b> &nbsp;·&nbsp; widened: <b>${STD.widened[k]}</b></div>`;
  }
  if (cell.gold != null) {
    h += `<div class="tt-gold"><span class="tt-label">reference:</span> ${esc(cell.gold)}`;
    if (cell.gold_source) h += `<div class="tt-src">source: ${esc(cell.gold_source)}</div>`;
    h += `</div>`;
  } else {
    h += `<div class="tt-gold tt-src">no reference value (unscored)</div>`;
  }
  if (cell.evidence && cell.evidence.length) {
    h += `<div class="tt-ev"><span class="tt-label">evidence (${cell.evidence.length}):</span>`;
    for (const e of cell.evidence) {
      const loc = [e.sample, e.section, (e.page!=null?('p.'+e.page):null)].filter(Boolean).map(esc).join(' · ');
      h += `<div style="margin-top:4px"><div class="q">“${esc(e.quote)}”</div>${loc?`<div class="meta">${loc}</div>`:''}</div>`;
    }
    h += `</div>`;
  }
  tt.innerHTML = h; tt.style.display='block';
  const r = tt.getBoundingClientRect(), vw=innerWidth, vh=innerHeight;
  let left=x+12, top=y+12;
  if (left+r.width>vw-10) left=x-r.width-12;
  if (top+r.height>vh-10) top=y-r.height-12;
  tt.style.left=Math.max(10,left)+'px'; tt.style.top=Math.max(10,top)+'px';
}
function hideTip(){ tt.style.display='none'; tt.classList.remove('pinned'); }

// ---- table ----
function buildTable(visible){
  const hr = document.getElementById('headerRow');
  hr.innerHTML = '<th>Paper</th>' + fields.map(f => `<th class="${evald.has(f)?'evald':''}" title="${esc(f)}">${esc(f)}</th>`).join('');
  const rows = visible.map(pid => {
    const p = byId[pid];
    let tr = `<tr><td title="${esc(pid)}">${esc(pid)}</td>`;
    for (const f of fields) {
      const cell = p.cells[f];
      tr += `<td><div class="cell ${cellColor(cell&&cell.klass)}" data-p="${esc(pid)}" data-f="${esc(f)}">${renderCell(cell)}</div></td>`;
    }
    return tr + '</tr>';
  });
  document.getElementById('tableBody').innerHTML = rows.join('');
  document.getElementById('paperCount').textContent = visible.length + ' papers';
  document.querySelectorAll('.cell').forEach(c => {
    c.addEventListener('mouseenter', e => { if(!pinned) showTip(c.dataset.p, c.dataset.f, e.clientX, e.clientY); });
    c.addEventListener('mousemove', e => { if(!pinned) showTip(c.dataset.p, c.dataset.f, e.clientX, e.clientY); });
    c.addEventListener('mouseleave', () => { if(!pinned) hideTip(); });
    c.addEventListener('click', e => {
      e.stopPropagation();
      const same = pinned && pinned.p===c.dataset.p && pinned.f===c.dataset.f;
      document.querySelectorAll('.cell.pinned').forEach(b=>b.classList.remove('pinned'));
      if (same) { pinned=null; hideTip(); }
      else { pinned={p:c.dataset.p,f:c.dataset.f}; c.classList.add('pinned'); showTip(c.dataset.p,c.dataset.f,e.clientX,e.clientY); tt.classList.add('pinned'); }
    });
  });
}
document.addEventListener('click', e => {
  if (pinned && !e.target.closest('.cell') && !e.target.closest('.tooltip')) {
    pinned=null; hideTip(); document.querySelectorAll('.cell.pinned').forEach(b=>b.classList.remove('pinned'));
  }
});

const viewMode=document.getElementById('viewMode'), paperSelect=document.getElementById('paperSelect'), searchBox=document.getElementById('searchBox');
papers.forEach(p => { const o=document.createElement('option'); o.value=p.id; o.textContent=p.id; paperSelect.appendChild(o); });
function refresh(){
  const search=searchBox.value.trim().toLowerCase();
  let vis;
  if (viewMode.value==='single'){ paperSelect.style.display=''; vis=[paperSelect.value]; }
  else { paperSelect.style.display='none'; vis=papers.map(p=>p.id); }
  if (search) vis=vis.filter(id=>id.toLowerCase().includes(search));
  pinned=null; hideTip(); buildTable(vis);
}
viewMode.onchange=refresh; paperSelect.onchange=refresh; searchBox.oninput=refresh;
document.querySelectorAll('input[name=std]').forEach(r => r.addEventListener('change', e => {
  std = e.target.value; markActivePanel(); refresh();
}));

markActivePanel();
refresh();
</script>
</body>
</html>
"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ma", required=True, choices=sorted(MODULES), help="which meta-analysis")
    ap.add_argument("--out", required=True, help="output HTML path")
    ap.add_argument("--runs", default=None, help="override the runs dir")
    args = ap.parse_args()

    runs = Path(args.runs) if args.runs else None
    data = build(args.ma, runs)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_html(data), encoding="utf-8")

    s = data["summary"]["overall"]
    print(
        f"{data['ma_name']}: {len(data['papers'])} papers, {len(data['fields'])} fields, "
        f"{len(data['assets'])} assets | "
        f"strict F1 {s['strict']['f1']:.3f} / widened F1 {s['widened']['f1']:.3f} -> {out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
