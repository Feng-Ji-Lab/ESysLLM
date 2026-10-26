"""Quality inspector for Marker output (Jansen benchmark).

For each PDF, check:
  * JSON loads, has children, page count plausible vs original PDF
  * Total extracted text length (raw)
  * Section keywords found (abstract / method(s) / results / discussion /
    references / appendix) — flag if too few
  * Block-type histogram (Page, Text, Table, Figure, Equation, …)
  * Tables PNG count vs Marker's `Table` block count
  * Figure PNG count vs Marker's `Figure` block count
  * `_meta.json`: llm_used / llm_service / model
  * Source PDF page count (via pypdf) — sanity vs JSON pages

Outputs: TSV summary to stdout + Markdown report to docs/reports/.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

import pypdf

ROOT = Path("/projects/code/meta_analysis_agent")
PROCESSED = ROOT / "data" / "processed"
RAW = ROOT / "data" / "raw"
REPORT = ROOT / "docs" / "reports" / "2026-05-28-marker-quality-report.md"

SECTION_RE = {
    "abstract":   re.compile(r"\babstract\b", re.IGNORECASE),
    "introduction": re.compile(r"\bintroduction\b", re.IGNORECASE),
    "method":     re.compile(r"\bmethods?\b", re.IGNORECASE),
    "result":     re.compile(r"\bresults?\b", re.IGNORECASE),
    "discussion": re.compile(r"\bdiscussion\b", re.IGNORECASE),
    "reference":  re.compile(r"\breferences?\b", re.IGNORECASE),
    "table":      re.compile(r"\btable [0-9]\b", re.IGNORECASE),
}


def walk_blocks(node: Any) -> Iterable[dict]:
    if isinstance(node, dict):
        yield node
        for c in node.get("children") or []:
            yield from walk_blocks(c)
    elif isinstance(node, list):
        for c in node:
            yield from walk_blocks(c)


def extract_text_and_blocks(json_data: dict) -> tuple[str, Counter, int]:
    """Return (concatenated text, block-type histogram, page count)."""
    hist: Counter = Counter()
    text_parts: list[str] = []
    n_pages = 0
    for block in walk_blocks(json_data):
        bt = block.get("block_type")
        if bt:
            hist[bt] += 1
        if bt == "Page":
            n_pages += 1
        # Marker stores plain text in html field as well as in some text fields
        for k in ("text", "html"):
            v = block.get(k)
            if isinstance(v, str) and v:
                text_parts.append(v)
    raw_text = " ".join(text_parts)
    # Strip HTML tags conservatively for keyword search
    raw_text = re.sub(r"<[^>]+>", " ", raw_text)
    raw_text = re.sub(r"\s+", " ", raw_text).strip()
    return raw_text, hist, n_pages


def count_pdf_pages(pdf_path: Path) -> int:
    try:
        return len(pypdf.PdfReader(str(pdf_path)).pages)
    except Exception:
        return -1


def inspect(bench: str, stem: str) -> dict:
    bench_dir = PROCESSED / bench / stem
    json_path = bench_dir / f"{stem}.json"
    meta_path = bench_dir / f"{stem}_meta.json"
    pdf_path = RAW / bench / f"{stem}.pdf"

    out = {
        "bench": bench, "key": stem,
        "json_kb": 0,
        "n_pages_json": 0, "n_pages_pdf": count_pdf_pages(pdf_path),
        "n_blocks": 0, "text_len": 0,
        "sections_found": "", "n_sections_found": 0,
        "n_table_blocks": 0, "n_table_png": 0,
        "n_figure_blocks": 0, "n_figure_png": 0,
        "n_images": 0,
        "llm_service": "", "llm_model": "",
        "block_hist": "",
        "issues": [],
    }

    if not json_path.exists():
        out["issues"].append("JSON missing")
        return out
    out["json_kb"] = json_path.stat().st_size // 1024
    try:
        json_data = json.loads(json_path.read_text(encoding="utf-8"))
    except Exception as e:
        out["issues"].append(f"JSON parse error: {e}")
        return out

    text, hist, n_pages = extract_text_and_blocks(json_data)
    out["n_pages_json"] = n_pages
    out["n_blocks"] = sum(hist.values())
    out["text_len"] = len(text)
    out["n_table_blocks"] = hist.get("Table", 0)
    out["n_figure_blocks"] = hist.get("Figure", 0) + hist.get("Picture", 0)
    out["block_hist"] = ",".join(f"{k}={v}" for k, v in hist.most_common(8))

    # Section presence
    found = [name for name, rx in SECTION_RE.items() if rx.search(text)]
    out["sections_found"] = "|".join(found)
    out["n_sections_found"] = len(found)

    # PNG counts
    table_pngs = list((bench_dir / "tables").glob("*.png")) if (bench_dir / "tables").exists() else []
    out["n_table_png"] = len(table_pngs)
    figure_pngs = list((bench_dir / "figures").glob("*.png")) if (bench_dir / "figures").exists() else []
    out["n_figure_png"] = len(figure_pngs)
    if (bench_dir / "images").exists():
        out["n_images"] = len(list((bench_dir / "images").glob("*.*")))

    # meta
    if meta_path.exists():
        try:
            m = json.loads(meta_path.read_text(encoding="utf-8"))
            out["llm_service"] = m.get("llm_service") or ""
            out["llm_model"] = m.get("llm_model") or ""
        except Exception:
            pass

    # Issue flags
    if out["n_pages_json"] == 0:
        out["issues"].append("0 pages in JSON")
    if out["n_pages_pdf"] > 0 and out["n_pages_json"] > 0:
        if abs(out["n_pages_json"] - out["n_pages_pdf"]) > 1:
            out["issues"].append(
                f"page count mismatch (json={out['n_pages_json']} vs pdf={out['n_pages_pdf']})"
            )
    if out["text_len"] < 5000:
        out["issues"].append(f"very short text ({out['text_len']} chars)")
    if out["n_sections_found"] < 3:
        out["issues"].append(f"few sections detected ({out['n_sections_found']}/7)")
    if out["llm_service"] != "vertex":
        out["issues"].append(f"llm_service={out['llm_service'] or 'unset'}")
    if out["n_table_blocks"] > 0 and out["n_table_png"] == 0:
        out["issues"].append("Table block(s) but 0 PNG")
    if out["n_figure_blocks"] > 0 and out["n_figure_png"] == 0:
        out["issues"].append("Figure block(s) but 0 PNG")

    return out


def main() -> None:
    rows: list[dict] = []
    for bench in ("hien2024", "ng2023", "vu2024"):
        for d in sorted((PROCESSED / bench).iterdir()):
            if not d.is_dir():
                continue
            rows.append(inspect(bench, d.name))

    # Stdout summary
    print(f"{'KEY':24s} {'JSON':>5s} {'pgJSON':>6s} {'pgPDF':>5s} {'text':>6s} {'sect':>4s} {'tBlk':>4s} {'tPNG':>4s} {'fBlk':>4s} {'fPNG':>4s}  ISSUES")
    print("-" * 110)
    n_clean = n_issue = 0
    for r in rows:
        flag = "" if not r["issues"] else "  ⚠ " + " | ".join(r["issues"])
        if r["issues"]:
            n_issue += 1
        else:
            n_clean += 1
        print(f"{r['bench'][:3]}/{r['key']:<19s} {r['json_kb']:>5d} {r['n_pages_json']:>6d} {r['n_pages_pdf']:>5d} {r['text_len']//1000:>5d}K {r['n_sections_found']:>4d} {r['n_table_blocks']:>4d} {r['n_table_png']:>4d} {r['n_figure_blocks']:>4d} {r['n_figure_png']:>4d}{flag}")

    print()
    print(f"Clean: {n_clean} / Issues: {n_issue} / Total: {len(rows)}")

    # Markdown report
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    md_lines = [
        "# Marker Quality Report — Jansen Benchmark (2026-05-28)",
        "",
        f"Inspected {len(rows)} Marker outputs from `{PROCESSED.relative_to(ROOT)}`.",
        "",
        f"**Clean: {n_clean} / Issues flagged: {n_issue}**",
        "",
        "## Per-paper table",
        "",
        "| key | JSON KB | pages (JSON/PDF) | text chars | sections found | tables blk/PNG | figs blk/PNG | images | issues |",
        "|---|---:|---|---:|---|---|---|---:|---|",
    ]
    for r in rows:
        issues = "; ".join(r["issues"]) if r["issues"] else "—"
        md_lines.append(
            f"| `{r['bench']}/{r['key']}` "
            f"| {r['json_kb']} | {r['n_pages_json']} / {r['n_pages_pdf']} | {r['text_len']} "
            f"| {r['n_sections_found']}/7 ({r['sections_found']}) "
            f"| {r['n_table_blocks']} / {r['n_table_png']} "
            f"| {r['n_figure_blocks']} / {r['n_figure_png']} "
            f"| {r['n_images']} | {issues} |"
        )
    md_lines.append("")
    md_lines.append("## Block-type histograms (top 8 per paper)")
    md_lines.append("")
    for r in rows:
        md_lines.append(f"- `{r['bench']}/{r['key']}`: {r['block_hist']}")
    REPORT.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    print(f"\nFull report: {REPORT}")


if __name__ == "__main__":
    main()
