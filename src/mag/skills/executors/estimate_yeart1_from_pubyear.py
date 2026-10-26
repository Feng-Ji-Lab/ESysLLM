"""Executor: estimate yearT1 when unreported, replicating the Buecker (2023) gold rule.

The meta-analysts' coding manual defines, for `infoYearT1 = 3 (Estimated)`:
    Year of Time 1 = publication_year - (3 years + interval between Time 1 and the
                     last assessment included in the study)
i.e. yearT1 = pub_year - 3 - span. This executor applies that rule ONLY when the
extractor did not surface a stated year (yearT1 is None/"None"). A stated or
already-resolved year is left untouched. The publication year is supplied via
`context["publication_year"]` (sourced from the study's reference-list entry and
injected per paper by the orchestrator). The span (T1->last wave) is estimated from
the extracted payload: (max wave number - 1) * lag; falls back to 2 years — the
gold-typical value — when waves/lag are unavailable.
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING

from mag.models import CellValue, Derivation

if TYPE_CHECKING:
    from mag.models import Field
    from mag.skills.loader import Skill

_DEFAULT_SPAN = 2.0  # gold-typical interval when the study span cannot be derived


def _estimate_span(fields: dict[str, Field]) -> tuple[float, str]:
    waves: set[int] = set()
    for fname in ("M_SWB", "Sample", "SD_SWB"):
        fld = fields.get(fname)
        if fld is None:
            continue
        for key in fld.cells:
            m = re.search(r"wave\s*(\d+)", key, re.I)
            if m:
                waves.add(int(m.group(1)))
    n_waves = max(waves) if waves else None
    lag_fld = fields.get("lag")
    lag = lag_fld.paper_value.value if lag_fld and lag_fld.paper_value else None
    if n_waves and n_waves >= 2 and isinstance(lag, (int, float)):
        return max(1.0, float(lag) * (n_waves - 1)), f"lag*{n_waves - 1}waves"
    return _DEFAULT_SPAN, "default"


def estimate_yeart1_from_pubyear(
    *, fields: dict[str, Field], target: str, skill: Skill, context: dict | None = None
) -> Field:
    yt = fields[target]
    cur = yt.paper_value.value if yt.paper_value else None
    ctx = context or {}
    pub = ctx.get("publication_year")
    if pub is None:
        return yt
    def _asint(x):
        try:
            return int(round(float(x)))
        except (TypeError, ValueError):
            return None
    # Fire ONLY when the extractor left yearT1 unresolved (None/"") or produced an
    # implausible value (later than publication — a hallucinated/pub-year guess). A
    # concrete extracted year is trusted: it came from real Stage-1 evidence.
    #
    # NOTE on the provenance override: the ideal rule is "if infoYearT1=='estimated',
    # override even a plausible stated year (e.g. a background-citation year like
    # Carmel's 1994)". That is only sound when infoYearT1 is itself EXTRACTED from
    # evidence. In the Stage-2 re-aggregation path infoYearT1 has no candidates and the
    # aggregator defaults it to a no-evidence "estimated" for every paper — using that
    # to override concrete years regressed the 'given' cases (Armenta 2002->2005,
    # Berg 1991->2002). So we do NOT trigger on infoYearT1 here; enabling the override
    # requires a full Stage-1 re-extract that populates the indicator (see docs report).
    cur_i = _asint(cur)
    estimate = (
        cur in (None, "None", "")
        or (cur_i is not None and cur_i > int(round(float(pub))))
    )
    if not estimate:
        return yt  # a concrete, plausible stated year is respected
    span, span_src = _estimate_span(fields)
    est = int(round(float(pub))) - 3 - int(round(span))
    return yt.model_copy(update={
        "paper_value": CellValue(
            value=est,
            derivation=Derivation(
                kind="infer_constant",
                skill_name=skill.name,
                formula="yearT1 = publication_year - 3 - span",
                inputs={"publication_year": pub, "span": round(span, 2), "span_source": span_src},
                note="Buecker gold estimation rule for an unreported (Estimated) baseline year",
            ),
            confidence=0.4,
        )
    })
