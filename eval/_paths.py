"""Single source of truth for where scorers find run outputs and third-party gold.

The scripts under ``scripts/`` and the gold libraries under ``eval/_dashboard``
were written against two private directories (``data/runs/<run>`` for pipeline
outputs, ``Jansen2025/`` for the benchmark archive). The public release ships
the as-run outputs under ``results/<ma>/raw`` and only the handful of
third-party files the scorers open under ``eval/_jansen`` (same relative
layout as the OSF archive, see ``eval/_jansen/PROVENANCE.md``). Every scorer
resolves its inputs through this module, so nothing else had to change.

New extraction runs still land in ``data/runs/`` (gitignored); ``run_dir``
falls back to that location for any run name not listed here.
"""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
JANSEN_DIR = REPO / "eval" / "_jansen"
RESULTS_DIR = REPO / "results"

# run name used while the experiments were executed -> shipped location
_RUN_DIRS: dict[str, Path] = {
    "jansen_vu2024": RESULTS_DIR / "vu2024" / "raw",
    "jansen_ng2023": RESULTS_DIR / "ng2023" / "raw",
    "jansen_bennett2023_v5": RESULTS_DIR / "bennett2023" / "raw" / "v5",
    "jansen_bennett2023_new10": RESULTS_DIR / "bennett2023" / "raw" / "new10",
    "jansen_bennett2023_rest43": RESULTS_DIR / "bennett2023" / "raw" / "rest43",
    "jansen_bowes2023": RESULTS_DIR / "bowes2023" / "raw",
    "jansen_buecker2023_v6": RESULTS_DIR / "buecker2023" / "raw",
}


def run_dir(name: str) -> Path:
    """Directory holding the per-paper outputs of run ``name``."""
    return _RUN_DIRS.get(name, REPO / "data" / "runs" / name)
