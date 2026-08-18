"""Single source of truth for ML/DL/NLP/RecSys hyperparameters.

These are reproducibility-critical values, not runtime settings — they live
here as plain literals in version control rather than in pydantic_settings
(env-overridable config is for infra knobs like OPENAI_BASE_URL, which stays
in app.core.config.Settings). Every script/service that trains, precomputes,
or evaluates a model imports its hyperparameters from here instead of
hardcoding them, so a value only ever needs to change in one place, and
serving code can never silently drift from what a model was actually built
with.
"""

# Used everywhere a stochastic step needs to be reproducible: TruncatedSVD,
# ALS, the CF eval train/test split, and the DeepWalk random-walk generation.
RANDOM_SEED = 42


class SearchConfig:
    """Lexical (tsvector) + semantic (pgvector) + hybrid (RRF) search."""

    # MLX-converted Qwen3-Embedding-0.6B, served via the `mlx-embeddings`
    # package (decoder-based, last-token pooling, 1024-dim native output,
    # 32K token context — replaces all-MiniLM-L6-v2 as of this pass).
    # 4-bit DWQ (dynamic-range weight quantization) chosen over mxfp8 for
    # throughput: mxfp8 measured ~0.47s/doc on this hardware (a ~28K-game
    # catalog would take 3-4h) — MLX's fast-matmul path is more mature for
    # 4-bit than for mxfp8, and DWQ specifically targets retaining
    # near-full-precision quality despite the drop to 4-bit, unlike naive
    # round-to-nearest quantization. Swap this string to try mxfp8 or the
    # full-precision original if quality regresses noticeably.
    EMBEDDING_MODEL = "mlx-community/Qwen3-Embedding-0.6B-4bit-DWQ"
    # Reciprocal Rank Fusion constant combining lexical/semantic ranks.
    RRF_K = 60
    # Candidate pool pulled from each retrieval leg before RRF + filtering.
    CANDIDATE_POOL_SIZE = 100
    # Embedding document construction (scripts/update_embeddings.py).
    # Tried raising this to 4,000 on the reasoning that Qwen3's 32K context
    # *can* handle longer input — but measured against the actual catalog,
    # the median document is identical at 1,500 vs 4,000 chars (316 tokens
    # either way — most descriptions are already short), while 4,000 nearly
    # triples the tail (p99 1,146 vs 549 tokens, max 1,313 vs 553). A long
    # document also isn't free for embedding *quality*: pooling a long,
    # often flavor-text-heavy BGG description into one fixed-size vector
    # dilutes the distinctive signal (which Themes/Mechanics/Categories/
    # Subdomains/Families/Experience already carry as structured fields)
    # toward a blander, less discriminative centroid. Reverted to the value
    # already known to produce working, evaluated search results under
    # all-MiniLM-L6-v2 (which itself only ever saw ~256 tokens/~1,000-1,200
    # chars of it, truncated internally regardless of input length).
    DESCRIPTION_TRUNCATE_CHARS = 1500
    # Tokenizer max_length passed to mlx_embeddings' batch_encode_plus.
    # Measured p99=549, max=553 tokens at DESCRIPTION_TRUNCATE_CHARS=1500
    # (500-doc sample) — 768 is a real backstop with headroom, not 2,048
    # of mostly-unused budget every batch pads toward.
    EMBED_MAX_TOKENS = 768
    # Was 500 under all-MiniLM-L6-v2 (22M params, 256-token cap — cheap to
    # batch large). Qwen3-Embedding-0.6B is a much larger decoder model over
    # much longer sequences, so a large batch risks memory pressure on
    # unified memory; start conservative and raise it if your hardware
    # handles it comfortably.
    EMBED_BATCH_SIZE = 32

    # Instruction-aware embedding models (e.g. Qwen3-Embedding) are trained
    # for *asymmetric* retrieval: the query gets an instruction prefix, the
    # document does not. Models not in this set (e.g. all-MiniLM-L6-v2)
    # never had this format in training, so it must not be applied to them.
    INSTRUCTION_AWARE_MODELS = {"mlx-community/Qwen3-Embedding-0.6B-4bit-DWQ"}
    QUERY_INSTRUCTION = (
        "Instruct: Given a search query about board games, retrieve game "
        "descriptions that best match the query\nQuery: {query}"
    )

    # Weight/playtime buckets embedded as short text phrases in the document
    # (scripts/update_embeddings.py::build_structured_document), so a query
    # like "heavy strategy game" or "quick filler" has textual signal to
    # match against. Ranges are kept identical, by hand, to the filter
    # presets in frontend/src/pages/GamesList.tsx (search for 'Light (1-2)')
    # so the UI and the embedding vocabulary never disagree on what "light"
    # or "heavy" means. (min, max, phrase) — max is exclusive except the
    # last bucket; None means unbounded.
    WEIGHT_BUCKETS = [
        (1.0, 2.0, "light strategy game, easy to learn"),
        (2.0, 3.5, "medium-weight strategy game"),
        (3.5, 5.0, "heavy strategy game, high complexity"),
    ]
    PLAYTIME_BUCKETS = [
        (0, 30, "quick game, under 30 minutes"),
        (30, 60, "30 to 60 minute game"),
        (60, 120, "60 to 120 minute game"),
        (120, None, "long game, over 2 hours"),
    ]


class ABSAConfig:
    """Aspect-based sentiment extraction (DeBERTa zero-shot classifier)."""

    MODEL_NAME = "yangheng/deberta-v3-large-absa-v1.1"
    # Fixed 22-aspect taxonomy — every extraction run classifies against
    # exactly this list, never a subset, so aggregates stay comparable.
    TAXONOMY = [
        "Gameplay", "Mechanics", "Strategy", "Theme", "Immersion", "Replayability",
        "Components", "Artwork", "Production Quality", "Rulebook", "Setup", "Teardown",
        "Learning Curve", "Complexity", "Downtime", "Player Interaction", "Balance",
        "Luck", "Player Count", "Solo Play", "Game Length", "Value",
    ]
    # Aspects are classified in chunks of this size per review to bound peak
    # GPU/MPS memory (22 aspects doesn't divide evenly — last chunk is smaller).
    BATCH_SIZE = 11
    # A predicted sentiment is only kept if the winning class's softmax
    # probability clears this bar; ties/uncertain calls are dropped.
    WINNER_PROB_THRESHOLD = 0.5

    # Review quality/eligibility filter (compute_quality_score), shared by
    # scripts/absa_filter.py, generate_stratified_sample.py, absa_extract_hf.py.
    QUALITY_SCORE_THRESHOLD = 0.6
    QUALITY_LENGTH_NORM_WORDS = 100.0
    QUALITY_SPAM_PENALTY = 0.5
    QUALITY_SPAM_PATTERN = r"(.)\1{4,}"
    QUALITY_ASPECT_SIGNAL_CAP = 0.4
    QUALITY_ASPECT_SIGNAL_STEP = 0.1
    QUALITY_GAME_WORDS = {
        "rulebook", "setup", "cards", "component", "components", "theme",
        "mechanic", "player", "time", "luck", "balance",
    }

    # fastText language-ID model — pinned external download, not a trained
    # artifact, so it's tracked here by URL/filename rather than in MLflow.
    FASTTEXT_MODEL_URL = "https://dl.fbaipublicfiles.com/fasttext/supervised-models/lid.176.ftz"
    FASTTEXT_MODEL_FILENAME = "lid.176.ftz"

    # Stratified sampling for the ABSA pilot corpus (generate_stratified_sample.py).
    SAMPLE_TOP_N_GAMES = 100
    SAMPLE_TARGET_PER_GAME = 100
    SAMPLE_NEGATIVE_RATING_MAX = 4.0
    SAMPLE_POSITIVE_RATING_MIN = 7.0


class SummarizationConfig:
    """LLM-generated "Customers say" per-game summaries."""

    MIN_REVIEWS_FOR_ABSA = 15
    MIN_ASPECT_MENTIONS = 5
    TOP_K_ASPECTS = 5
    MAX_REVIEWS_PER_ASPECT = 100
    TEMPERATURE = 0.0
    MAX_TOKENS = 2048


class RecommenderConfig:
    """Content-based, collaborative, and graph recommenders (10 model IDs)."""

    # --- Collaborative filtering (real fit() steps) ---
    CF_ITEM_COSINE_MIN_SHARED_USERS = 50
    CF_SVD_N_FACTORS = 50
    CF_ALS_FACTORS = 50
    CF_ALS_ITERATIONS = 15
    CF_ALS_REGULARIZATION = 0.1

    # --- Content-based (similarity only, no fit step) ---
    # metadata = 0.7 * category/mechanic TF-IDF sim + 0.3 * numeric-feature sim
    METADATA_CATEGORICAL_WEIGHT = 0.7
    METADATA_NUMERIC_WEIGHT = 0.3
    TFIDF_MAX_FEATURES = 10000
    # hybrid = weighted blend of embedding/metadata/tfidf similarity + quality
    HYBRID_WEIGHTS = {"embedding": 0.45, "metadata": 0.25, "tfidf": 0.15, "quality": 0.15}
    # quality score blend (rank-based + rating-based), both min-max normalized
    QUALITY_RANK_WEIGHT = 0.5
    QUALITY_RATING_WEIGHT = 0.5
    RECS_PER_MODEL_LIMIT = 10

    # --- Graph-based ---
    GRAPH_JACCARD_WEIGHTS = {
        "mechanics": 0.4, "categories": 0.3, "designers": 0.05,
        "publishers": 0.025, "artists": 0.025,
    }
    # DeepWalk-via-Word2Vec graph embedding (model id: "deepwalk" — this
    # replaces the real, unused node2vec PyPI-package path, which never
    # produced an artifact and has been removed).
    DEEPWALK_NUM_WALKS = 10
    DEEPWALK_WALK_LENGTH = 10
    DEEPWALK_VECTOR_SIZE = 64
    DEEPWALK_WINDOW = 5
    DEEPWALK_EPOCHS = 1
    DEEPWALK_MIN_COUNT = 1


class AssistantConfig:
    """LLM-powered natural-language query intent parsing."""

    TEMPERATURE = 0.0
    MAX_TOKENS = 4096
