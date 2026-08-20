"""Cheap, model-free review quality filtering.

Purpose: shrink the review pool *before* the genuinely expensive step
(DeBERTa ABSA classification), not classify text quality in the abstract.
Every signal here is a deterministic hash, count, or ratio over the text —
no model inference, no training, no labeled data — so this is fast enough
to run over the full ~4.2M-review corpus as a pre-filter. The one exception,
stemming (NLTK's SnowballStemmer), is a rule-based suffix-stripping
algorithm, not a learned model, and is only used for the one-time corpus
statistics pass (scripts/build_review_quality_vocab.py) and at per-review
scoring time for the specificity signal — never per-review for anything
performance-critical enough to matter.

Design, in pipeline order (see docs/ml/model-cards/absa-deberta.md):
  1. Language gate       — reuses reviews.language/language_confidence
  2. Hard filters         — binary pass/fail on categorically unusable text
  3. Dedup (exact + near) — SimHash, caller-managed (stateful across a run)
  4. Weighted score       — information density, lexical diversity, domain
                            specificity, boilerplate penalty
"""
import hashlib
import json
import os
import re
import unicodedata
from collections.abc import Iterable

import nltk
from nltk.corpus import stopwords as nltk_stopwords
from nltk.sentiment import SentimentIntensityAnalyzer
from nltk.stem import SnowballStemmer
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

from app.core.ml_config import ABSAConfig

# Same tokenization regex TfidfVectorizer uses elsewhere in this repo
# (scripts/precompute_content_recommendations.py) — kept consistent rather
# than introducing a second tokenization convention. Fast, stdlib-only.
_TOKEN_PATTERN = re.compile(r"(?u)\b\w\w+\b")


def _ensure_nltk_stopwords() -> None:
    try:
        nltk_stopwords.words("english")
    except LookupError:
        nltk.download("stopwords", quiet=True)


_ensure_nltk_stopwords()

# Union of both, not either alone — sklearn's and NLTK's English stopword
# lists don't fully overlap; combining them is a strict improvement in
# coverage for zero extra runtime cost (still just a frozenset lookup).
STOPWORDS: set[str] = set(ENGLISH_STOP_WORDS) | set(nltk_stopwords.words("english"))

_stemmer = SnowballStemmer("english")


def _ensure_vader_lexicon() -> None:
    try:
        SentimentIntensityAnalyzer()
    except LookupError:
        nltk.download("vader_lexicon", quiet=True)


_ensure_vader_lexicon()
# VADER — a fixed, hand-built lexicon + rule-based scorer (not trained by
# us; same category as fastText's pretrained language model), specifically
# designed for short, informal text like this. Added after finding that
# stopword-ratio/density (this module's original signals) can't reliably
# tell a genuine short opinion ("Cool little drafting game.", zero
# stopwords) apart from a metadata/collection-log fragment ("Received
# 04/08/2023", also zero stopwords) — both are short and stopword-free, but
# only one expresses sentiment. compound == 0.0 means the lexicon matched
# *no* sentiment-bearing words at all, which is a real, if imperfect,
# signal: it catches most metadata/trade-log noise, but also misses some
# (a lexicon can't tell "best 3-4 players" apart from "this is the best
# game", and won't match a typo like "Wast" for "waste") — see
# docs/ml/model-cards/absa-deberta.md for the measured false-reject rate.
_sia = SentimentIntensityAnalyzer()


def has_detectable_sentiment(text: str) -> bool:
    if not text:
        return False
    return _sia.polarity_scores(text)["compound"] != 0.0


def stem(token: str) -> str:
    return _stemmer.stem(token)


def tokenize(text: str) -> list[str]:
    if not text:
        return []
    return _TOKEN_PATTERN.findall(text.lower())


def normalize_for_dedup(text: str) -> str:
    """Collapse case/punctuation/whitespace so near-identical formatting
    (extra spaces, different punctuation) doesn't defeat exact-dup matching."""
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def has_valid_unicode(text: str) -> bool:
    if not text:
        return True
    try:
        text.encode("utf-8").decode("utf-8")
    except (UnicodeDecodeError, UnicodeEncodeError):
        return False
    # Cheap proxy for corrupted encoding / garbage byte sequences: reject
    # text dominated by control/unassigned/private-use/surrogate characters.
    bad = sum(1 for ch in text if unicodedata.category(ch) in ("Cc", "Cn", "Co", "Cs"))
    return (bad / len(text)) < ABSAConfig.QUALITY_MAX_BAD_UNICODE_RATIO


def passes_language_filter(language: str | None, confidence: float | None) -> bool:
    """Reads the already-computed reviews.language/language_confidence
    columns (scripts/detect_languages.py) — does not run fastText itself.
    The old compute_quality_score() re-ran language ID from scratch on every
    call despite this column already existing; this is strictly redundant
    work removed, not new behavior."""
    return language == "en" and (confidence or 0.0) >= ABSAConfig.QUALITY_MIN_LANGUAGE_CONFIDENCE


def passes_hard_filters(text: str) -> bool:
    """Binary gate — categorically unusable text, no ambiguity. Deliberately
    cheap and run first: eliminates the most obvious garbage before any of
    the pricier per-review computation below runs."""
    if not text or not isinstance(text, str):
        return False
    stripped = text.strip()
    if len(stripped) < ABSAConfig.QUALITY_MIN_CHARS:
        return False
    if not has_valid_unicode(stripped):
        return False
    if not re.search(r"[a-zA-Z]", stripped):
        return False  # punctuation/digits/symbols only, no actual letters
    tokens = tokenize(stripped)
    if len(tokens) < ABSAConfig.QUALITY_MIN_TOKENS:
        return False
    if not has_detectable_sentiment(stripped):
        return False
    return True


# --- SimHash near-duplicate detection ---
# Deterministic hashing, not a trained model — two near-identical texts
# produce fingerprints with a small Hamming distance even when not
# byte-identical, catching reformatted/lightly-edited duplicate reviews
# that exact-match normalization (normalize_for_dedup) misses.

def _feature_hash(token: str) -> int:
    return int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)


def simhash(tokens: list[str], bits: int | None = None) -> int:
    bits = bits or ABSAConfig.QUALITY_SIMHASH_BITS
    if not tokens:
        return 0
    weights = [0] * bits
    for token in set(tokens):
        h = _feature_hash(token)
        for i in range(bits):
            weights[i] += 1 if (h >> i) & 1 else -1
    fingerprint = 0
    for i in range(bits):
        if weights[i] > 0:
            fingerprint |= (1 << i)
    return fingerprint


def hamming_distance(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def is_near_duplicate(fingerprint: int, seen_fingerprints: Iterable[int], max_distance: int | None = None) -> bool:
    max_distance = ABSAConfig.QUALITY_SIMHASH_MAX_DISTANCE if max_distance is None else max_distance
    return any(hamming_distance(fingerprint, other) <= max_distance for other in seen_fingerprints)


# --- Continuous quality signals ---

def information_density(tokens: list[str]) -> float:
    """content tokens / total tokens — non-stopword share of the review."""
    if not tokens:
        return 0.0
    content = [t for t in tokens if t not in STOPWORDS]
    return len(content) / len(tokens)


def lexical_diversity(tokens: list[str]) -> float:
    """unique tokens / total tokens (type-token ratio) — catches padded,
    repetitive text long enough to pass a pure length check
    ("good good good fun fun")."""
    if not tokens:
        return 0.0
    return len(set(tokens)) / len(tokens)


def specificity_score(tokens: list[str], domain_vocab: set[str] | None = None) -> float:
    """Fraction of (stemmed) tokens that are game-specific/content-bearing
    terms, per ABSAConfig.DOMAIN_VOCABULARY — a corpus-derived,
    human-curated list (see scripts/build_review_quality_vocab.py), not a
    hand-guessed one. Both the vocabulary and the tokens here are stemmed,
    so "component"/"components" match the same vocabulary entry."""
    if not tokens:
        return 0.0
    vocab = domain_vocab if domain_vocab is not None else ABSAConfig.DOMAIN_VOCABULARY
    if not vocab:
        return 0.0
    stems = [stem(t) for t in tokens]
    hits = sum(1 for s in stems if s in vocab)
    return min((hits / len(stems)) * ABSAConfig.QUALITY_SPECIFICITY_SCALE, 1.0)


def boilerplate_fraction(
    tokens: list[str],
    boilerplate_ngrams: set[tuple[str, ...]] | None = None,
    n: int | None = None,
) -> float:
    """Fraction of tokens falling inside a corpus-frequent n-gram — catches
    templated phrases reused across *different* users' reviews, not just
    whole-review duplicates (which dedup/SimHash already handles)."""
    n = n or ABSAConfig.BOILERPLATE_NGRAM_SIZE
    if boilerplate_ngrams is None or len(tokens) < n:
        return 0.0
    flagged = [False] * len(tokens)
    for i in range(len(tokens) - n + 1):
        if tuple(tokens[i:i + n]) in boilerplate_ngrams:
            for j in range(i, i + n):
                flagged[j] = True
    return sum(flagged) / len(tokens) if tokens else 0.0


_BOILERPLATE_NGRAMS_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "data", "boilerplate_ngrams.json"
)


def load_boilerplate_ngrams() -> set[tuple[str, ...]]:
    """Optional precomputed artifact (scripts/build_review_quality_vocab.py)
    — if it hasn't been built yet, the boilerplate signal just contributes
    nothing rather than failing. Shared by every script that scores review
    quality, so the path/format lives in one place."""
    if not os.path.exists(_BOILERPLATE_NGRAMS_PATH):
        return set()
    with open(_BOILERPLATE_NGRAMS_PATH) as f:
        return {tuple(g) for g in json.load(f)}


def compute_quality_score(
    text: str,
    domain_vocab: set[str] | None = None,
    boilerplate_ngrams: set[tuple[str, ...]] | None = None,
) -> float:
    """Weighted combination of the four continuous signals. Hard gates,
    language filtering, and dedup are applied separately upstream — they're
    binary pass/fail decisions, not inputs to a weighted score."""
    tokens = tokenize(text)
    if not tokens:
        return 0.0

    density = information_density(tokens)
    diversity = lexical_diversity(tokens)
    specificity = specificity_score(tokens, domain_vocab)
    boilerplate = boilerplate_fraction(tokens, boilerplate_ngrams)

    score = (
        ABSAConfig.QUALITY_DENSITY_WEIGHT * density
        + ABSAConfig.QUALITY_DIVERSITY_WEIGHT * diversity
        + ABSAConfig.QUALITY_SPECIFICITY_WEIGHT * specificity
        - ABSAConfig.QUALITY_BOILERPLATE_WEIGHT * boilerplate
    )
    return max(score, 0.0)
