"""Quote-vs-section grounding: detect Stage-1 candidates whose evidence quote
does not appear in the cited section (a hallucination signal)."""

from __future__ import annotations

import re

_TOKEN = re.compile(r"[a-z0-9]+")
_LEADING_MARKER = re.compile(r"^\s*\[[^\]]*\]\s*")

# Common English stopwords excluded from overlap — their presence or absence in
# both strings is coincidental and would skew the ratio (e.g. "from" appearing
# in both a fabricated quote and an unrelated section text).
_STOPWORDS: frozenset[str] = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "but",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "with",
        "by",
        "from",
        "as",
        "is",
        "was",
        "are",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "shall",
        "can",
        "not",
        "no",
        "nor",
        "so",
        "yet",
        "both",
        "either",
        "neither",
        "each",
        "that",
        "this",
        "these",
        "those",
        "it",
        "its",
        "they",
        "their",
        "them",
        "we",
        "our",
        "you",
        "your",
        "he",
        "she",
        "his",
        "her",
        "who",
        "which",
        "what",
        "when",
        "where",
        "how",
        "all",
        "any",
        "such",
        "than",
        "then",
        "if",
        "into",
        "about",
        "after",
        "before",
        "between",
        "up",
        "out",
        "also",
        "there",
    }
)


def _tokens(text: str) -> set[str]:
    return set(_TOKEN.findall((text or "").lower())) - _STOPWORDS


def quote_overlap(quote: str, section_text: str) -> float:
    """Fraction of the quote's tokens that appear in the section text.

    A leading [block_id] marker is stripped first. An empty quote returns 1.0
    (cannot judge → treat as grounded, never over-drop).
    """
    q = _LEADING_MARKER.sub("", quote or "")
    qt = _tokens(q)
    if not qt:
        return 1.0
    st = _tokens(section_text)
    return len(qt & st) / len(qt)


def is_grounded(quote: str, section_text: str, *, threshold: float = 0.1) -> bool:
    return quote_overlap(quote, section_text) >= threshold
