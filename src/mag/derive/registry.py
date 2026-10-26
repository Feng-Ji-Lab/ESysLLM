"""Explicit name→callable maps for skill executors and validators."""

from __future__ import annotations

from mag.skills.executors.estimate_yeart1_from_pubyear import estimate_yeart1_from_pubyear
from mag.skills.executors.infer_college_sample_100 import infer_college_sample_100
from mag.skills.executors.infer_ethnicity_from_country import infer_ethnicity_from_country
from mag.skills.executors.single_gender_fill import single_gender_fill
from mag.skills.executors.weighted_mean_total import compute_weighted_mean_total
from mag.skills.validators.total_geq_sum import total_geq_sum

EXECUTORS = {
    "compute_weighted_mean_total": compute_weighted_mean_total,
    "estimate_yeart1_from_pubyear": estimate_yeart1_from_pubyear,
    "infer_college_sample_100": infer_college_sample_100,
    "infer_ethnicity_from_country": infer_ethnicity_from_country,
    "single_gender_fill": single_gender_fill,
}

VALIDATORS = {
    "total_geq_sum": total_geq_sum,
}
