"""run_extract exposes a reusable extract_one + CLI arg parsing."""

from __future__ import annotations

from pathlib import Path

from scripts.run_extract import build_arg_parser


def test_arg_parser_resolves_paper_and_dirs():
    p = build_arg_parser()
    a = p.parse_args(
        [
            "--paper-id",
            "1Hurst2017",
            "--marker-dir",
            "/x/marker/1Hurst2017",
            "--out-dir",
            "/x/run/1Hurst2017",
        ]
    )
    assert a.paper_id == "1Hurst2017"
    assert a.marker_dir == Path("/x/marker/1Hurst2017")
    assert a.out_dir == Path("/x/run/1Hurst2017")
    assert a.schema == "bas-bmi"  # default
