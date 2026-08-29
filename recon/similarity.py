"""
Description Similarity and Fuzzy Token Matching Module for VaultRecon AI.
Evaluates tokenized matching, n-gram overlap, and normalized narrative extraction
for reconciling noisy bank transaction narratives against settlement/invoice references.
"""

import re
from typing import Set, List, Tuple


def normalize_financial_text(text: str) -> str:
    """Normalize text by converting to uppercase, stripping special characters."""
    if not text:
        return ""
    return re.sub(r"[^A-Z0-9]", " ", text.upper()).strip()


def extract_tokens(text: str, min_len: int = 3) -> Set[str]:
    """Extract alphanumeric tokens with length >= min_len."""
    norm = normalize_financial_text(text)
    return {t for t in norm.split() if len(t) >= min_len}


def generate_ngrams(text: str, n: int = 3) -> Set[str]:
    """Generate character n-grams from normalized text."""
    clean = re.sub(r"\s+", "", normalize_financial_text(text))
    if len(clean) < n:
        return {clean} if clean else set()
    return {clean[i : i + n] for i in range(len(clean) - n + 1)}


def token_overlap_score(s1: str, s2: str) -> float:
    """Compute Jaccard token overlap between two descriptions."""
    tokens1 = extract_tokens(s1)
    tokens2 = extract_tokens(s2)
    if not tokens1 or not tokens2:
        return 0.0
    intersection = tokens1.intersection(tokens2)
    union = tokens1.union(tokens2)
    return len(intersection) / len(union)


def ngram_jaccard_similarity(s1: str, s2: str, n: int = 3) -> float:
    """Compute character n-gram Jaccard similarity between two strings."""
    ngrams1 = generate_ngrams(s1, n)
    ngrams2 = generate_ngrams(s2, n)
    if not ngrams1 or not ngrams2:
        return 0.0
    return len(ngrams1.intersection(ngrams2)) / len(ngrams1.union(ngrams2))


def is_fuzzy_reference_match(narrative: str, reference: str, threshold: float = 0.5) -> Tuple[bool, float]:
    """
    Check if a reference string or key fragment appears inside a bank narrative.
    Returns (is_match, score).
    """
    norm_narrative = normalize_financial_text(narrative)
    norm_ref = normalize_financial_text(reference)

    # 1. Direct substring check
    if norm_ref and norm_ref in norm_narrative:
        return True, 1.0

    # 2. Token overlap check
    t_score = token_overlap_score(narrative, reference)
    if t_score >= threshold:
        return True, t_score

    # 3. N-gram similarity check
    ng_score = ngram_jaccard_similarity(narrative, reference, n=3)
    if ng_score >= threshold:
        return True, ng_score

    return False, max(t_score, ng_score)

