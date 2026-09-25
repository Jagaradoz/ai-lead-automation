"""
text_match.py
Keyword matching that works for both English and Thai.
Latin terms match on word boundaries (with an optional plural suffix) so
"store" does not match "restore"; Thai has no spaces, so Thai terms match as substrings.
"""

import re
from functools import lru_cache
from typing import Iterable

_THAI_RE = re.compile(r"[฀-๿]")


def has_thai(text: str) -> bool:
    return bool(_THAI_RE.search(text or ""))


@lru_cache(maxsize=2048)
def _term_pattern(term: str) -> re.Pattern:
    return re.compile(r"(?<!\w)" + re.escape(term) + r"(?:s|es)?(?!\w)")


def contains_term(text_lower: str, term: str) -> bool:
    term = term.strip().lower()
    if not term or not text_lower:
        return False
    if has_thai(term):
        return term in text_lower
    return bool(_term_pattern(term).search(text_lower))


def count_terms(text_lower: str, terms: Iterable[str]) -> int:
    return sum(1 for term in terms if contains_term(text_lower, term))


def first_term(text_lower: str, terms: Iterable[str]):
    return next((term for term in terms if contains_term(text_lower, term)), None)
