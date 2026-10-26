"""Core data contracts for the v2 (mag) pipeline. Stable across providers/stages/UIs."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, model_validator
from pydantic import Field as PField

Granularity = Literal["paragraph", "table_cell", "figure", "sentence"]
FieldScope = Literal["paper", "sample"]
PassKind = Literal["text", "asset"]
DerivationKind = Literal[
    "weighted_mean",
    "subscale_mean",
    "subgroup_mean",
    "infer_constant",
    "infer_single_gender",
    "select_priority",
    "passthrough",
]
ProviderName = Literal["gemini", "openai", "anthropic"]

# sample_label values that mean "this study has no distinct named sub-sample"
_UNLABELED_SAMPLE = ("", "single study", "main")


class SampleKey(BaseModel):
    """A study+sample identity. Frozen so it is hashable and reusable as a key."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    study_index: int
    sample_label: str

    @property
    def rendered(self) -> str:
        if self.sample_label.strip().lower() in _UNLABELED_SAMPLE:
            return f"Study {self.study_index}"
        return f"Study {self.study_index} - {self.sample_label}"


class EvidenceRecord(BaseModel):
    """Anchors an extracted value back to a Marker block."""

    model_config = ConfigDict(extra="forbid")

    pdf_name: str
    section_id: str
    section_title: str = ""
    block_id: str | None = None
    page: int | None = None
    study_index: int | None = None
    granularity: Granularity = "paragraph"
    quote: str = ""
    bbox: list[float] | None = PField(default=None, min_length=4, max_length=4)


class Derivation(BaseModel):
    """Provenance for a computed/inferred value (set in Stage 3)."""

    model_config = ConfigDict(extra="forbid")

    kind: DerivationKind
    skill_name: str
    inputs: dict[str, Any] = PField(default_factory=dict)
    formula: str = ""
    note: str = ""


class CellValue(BaseModel):
    """One scalar within a Cell, with its evidence and optional derivation."""

    model_config = ConfigDict(extra="forbid")

    value: int | float | str | None
    evidence: list[EvidenceRecord] = PField(default_factory=list)
    derivation: Derivation | None = None
    confidence: float = PField(default=0.0, ge=0.0, le=1.0)


class Cell(BaseModel):
    """Length-1 (non-gender) or length-3 [total, female, male] positional list. [] = absent."""

    model_config = ConfigDict(extra="forbid")

    values: list[CellValue] = PField(default_factory=list)


class Field(BaseModel):
    """One field across all samples (sample-scoped) or one paper-level value (paper-scoped)."""

    model_config = ConfigDict(extra="forbid")

    name: str
    scope: FieldScope
    gender_specific: bool = False
    cells: dict[str, Cell] = PField(default_factory=dict)  # keyed by SampleKey.rendered
    paper_value: CellValue | None = None

    @model_validator(mode="after")
    def _scope_shape(self) -> Field:
        if self.scope == "paper" and self.cells:
            raise ValueError("paper-scoped field must use paper_value, not cells")
        if self.scope == "sample" and self.paper_value is not None:
            raise ValueError("sample-scoped field must use cells, not paper_value")
        return self


class Warning(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    field_name: str | None = None
    sample_key: str | None = None


class RunMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    provider: ProviderName
    model: str
    schema_name: str
    schema_version: int
    skill_names: list[str] = PField(default_factory=list)
    started_at: datetime
    finished_at: datetime
    prompt_tokens: int = PField(default=0, ge=0)
    completion_tokens: int = PField(default=0, ge=0)
    passes: int = PField(default=0, ge=0)
    aggregator_passes: int = PField(default=0, ge=0)

    @model_validator(mode="after")
    def _ts(self) -> RunMeta:
        if self.finished_at < self.started_at:
            raise ValueError("finished_at must be >= started_at")
        return self


class PaperResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    paper_id: str
    pdf_path: str
    marker_output_dir: str
    samples: list[SampleKey] = PField(default_factory=list)
    fields: dict[str, Field] = PField(default_factory=dict)
    warnings: list[Warning] = PField(default_factory=list)
    run_meta: RunMeta


class FieldCandidate(BaseModel):
    """One field's loose extraction from a single section pass (Stage 1 output)."""

    model_config = ConfigDict(extra="forbid")

    field_name: str
    value: Any = None  # restored dict {sample_label: [...]}, scalar, or None
    value_by_gender: dict[str, Any] | None = None
    evidence: list[EvidenceRecord] = PField(default_factory=list)
    warning: str = ""
    pass_kind: PassKind
