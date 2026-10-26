"""Tests for the Vu/Ng evaluation dashboard builder.

The classifier tests are pure and always run. The builder tests exercise the
real run outputs (``data/runs/``, gitignored) and gold files (``Jansen2025/``,
untracked), so they skip cleanly on a checkout without those local artifacts.
"""

from __future__ import annotations

from collections import Counter

import pytest
from eval._dashboard import common

try:
    import pandas  # noqa: F401  -- availability probe; goldlibs import it at module load
    from eval._dashboard import build_dashboard as bd
    from eval._dashboard import goldlib_vu

    _HAVE_DEPS = True
except ImportError:
    _HAVE_DEPS = False


# --- pure classifier unit tests (no data/pandas) ----------------------------


@pytest.mark.unit
def test_classify_set():
    assert common.classify_set({1, 2}, {1, 2}) == "exact"
    assert common.classify_set({1, 2}, {1, 2, 3}) == "contains"
    assert common.classify_set({1, 2}, {1, 3}) == "wrong"
    assert common.classify_set({1, 2, 3}, {1, 2}) == "wrong"  # incomplete
    assert common.classify_set({1, 2}, set()) == "missing"
    assert common.classify_set(set(), set()) == "exact"
    assert common.classify_set(set(), {1}) == "wrong"  # over-extraction on NA


@pytest.mark.unit
def test_classify_multiset():
    assert common.classify_multiset(Counter([1, 1, 2]), Counter([1, 1, 2])) == "exact"
    assert common.classify_multiset(Counter([1, 2]), Counter([1, 2, 2])) == "contains"
    assert common.classify_multiset(Counter([1, 2]), Counter([1, 3])) == "wrong"
    assert common.classify_multiset(Counter([1]), Counter()) == "missing"
    assert common.classify_multiset(Counter(), Counter([1])) == "wrong"


@pytest.mark.unit
def test_classify_scalar():
    assert common.classify_scalar(matched=True, extracted_present=True) == "exact"
    assert common.classify_scalar(matched=False, extracted_present=True) == "wrong"
    assert common.classify_scalar(matched=False, extracted_present=False) == "missing"


@pytest.mark.unit
def test_widened_never_below_strict_by_construction():
    # widening only moves "contains" from IED -> CED; CED can only grow.
    c = {"exact": 3, "contains": 4, "wrong": 2, "missing": 1}
    s = bd._from_counts(c, "strict") if _HAVE_DEPS else None
    w = bd._from_counts(c, "widened") if _HAVE_DEPS else None
    if not _HAVE_DEPS:
        pytest.skip("builder import needs pandas")
    assert w["md"] == s["md"]  # missing count unchanged; only contains is promoted
    assert w["ced"] >= s["ced"]
    assert w["precision"] >= s["precision"]
    assert w["recall"] >= s["recall"]
    assert w["f1"] >= s["f1"]


# --- builder integration tests ----------------------------------------------


def _have(ma) -> bool:
    if not _HAVE_DEPS:
        return False
    mod = bd.MODULES[ma]
    return mod.RUNS.exists() and any(
        (d / "paper_target.json").exists() for d in mod.RUNS.iterdir() if d.is_dir()
    )


vu_only = pytest.mark.skipif(not _have("vu"), reason="Vu runs/gold not present")
ng_only = pytest.mark.skipif(not _have("ng"), reason="Ng runs/gold not present")

ALLOWED_KLASS = {"exact", "contains", "wrong", "missing", "neutral"}


@vu_only
@pytest.mark.integration
def test_vu_every_paper_and_valid_klasses():
    data = bd.build("vu")
    ids = {p["id"] for p in data["papers"]}
    expected = {
        d.name
        for d in goldlib_vu.RUNS.iterdir()
        if d.is_dir() and (d / "paper_target.json").exists()
    }
    assert ids == expected and len(ids) == 15
    for p in data["papers"]:
        for cell in p["cells"].values():
            assert cell["klass"] in ALLOWED_KLASS


@vu_only
@pytest.mark.integration
def test_vu_scalars_all_exact():
    data = bd.build("vu")
    for field in ("Design", "country", "info_cost"):
        c = data["summary"]["per_field"][field]["counts"]
        assert c["exact"] == 15 and c["contains"] == c["wrong"] == c["missing"] == 0, (field, c)
        assert data["summary"]["per_field"][field]["strict"]["f1"] == 1.0


@vu_only
@pytest.mark.integration
def test_vu_conrads_design_exact_with_evidence():
    data = bd.build("vu")
    design = next(p for p in data["papers"] if p["id"] == "Conrads2013")["cells"]["Design"]
    assert design["klass"] == "exact"
    assert design["gold"] == "between-subject"
    assert design["gold_source"].startswith("WI_meta")
    assert design["evidence"] and design["evidence"][0]["quote"]


@ng_only
@pytest.mark.integration
def test_ng_every_paper_and_ipt_never_missing():
    data = bd.build("ng")
    assert len(data["papers"]) == 31
    assert data["summary"]["per_field"]["IPT"]["counts"]["missing"] == 0


@ng_only
@pytest.mark.integration
def test_ng_missing_reference_is_neutral():
    # Dietz2015 (studyid 20002) is absent from MeasureCharacteristics.xlsx.
    data = bd.build("ng")
    dietz = next(p for p in data["papers"] if p["id"] == "Dietz2015")["cells"]
    assert dietz["Source"]["klass"] == "neutral"
    assert dietz["Source"]["gold"] is None


@ng_only
@pytest.mark.integration
def test_widened_overall_ge_strict_on_real_data():
    data = bd.build("ng")
    s = data["summary"]["overall"]["strict"]
    w = data["summary"]["overall"]["widened"]
    assert w["ced"] >= s["ced"]
    assert w["f1"] >= s["f1"]


@vu_only
@pytest.mark.integration
def test_assets_collected():
    data = bd.build("vu")
    groups = {a["group"] for a in data["assets"]}
    assert {"Prompts", "Schema & field definitions", "Rules", "Ground-truth mapping"} <= groups
    titles = " ".join(a["title"] for a in data["assets"])
    assert "schemas/vu2024/prompts.yaml" in titles
    assert "schemas/vu2024/fields.json" in titles
    assert "rules/vu_" in titles  # a vu-specific rule pack
    # asset text is non-empty
    assert all(a["text"].strip() for a in data["assets"])


@vu_only
@pytest.mark.integration
def test_render_html_is_self_contained():
    html = bd.render_html(bd.build("vu"))
    assert "/* __DATA__ */" not in html
    assert "const DATA = {" in html
    assert "Vu 2024" in html
    assert "Customizations" in html
    assert "Widened" in html
