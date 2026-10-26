"""Quote-vs-section grounding helpers."""

from __future__ import annotations

from mag.extraction.grounding import is_grounded, quote_overlap


def test_quote_overlap_full_when_quote_in_section():
    section = "A total of 675 participants (367 women, 308 men) were analyzed."
    assert quote_overlap("675 participants 367 women", section) == 1.0


def test_quote_overlap_zero_for_fabrication():
    section = "Participants were 660 women from Kuala Lumpur, Malaysia."
    q = "200 undergraduate students recruited from the southeastern United States"
    assert quote_overlap(q, section) < 0.1


def test_quote_overlap_strips_leading_block_id_marker():
    section = "BMI was self-reported by participants."
    # leading [block_id] marker must not count against overlap
    assert quote_overlap("[009_method] BMI was self-reported", section) == 1.0


def test_is_grounded_threshold():
    section = "the mean age was twenty"
    assert is_grounded("the mean age", section, threshold=0.1)
    assert not is_grounded("entirely different fabricated text here", section, threshold=0.1)


def test_quote_overlap_empty_quote_is_grounded():
    # no quote → cannot judge → treat as grounded (overlap 1.0), don't over-drop
    assert quote_overlap("", "anything") == 1.0
