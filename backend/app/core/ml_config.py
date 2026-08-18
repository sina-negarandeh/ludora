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

    # base, not large — same trainer (yangheng) and training corpus (~180K
    # augmented SemEval-2014/2016 + MAMS examples) as the large checkpoint,
    # just a smaller architecture. Chosen for speed/coverage, not accuracy —
    # the domain mismatch (restaurant/laptop reviews, not board games) is
    # identical either size; this doesn't make that better or worse.
    MODEL_NAME = "yangheng/deberta-v3-base-absa-v1.1"
    # Fixed 17-aspect taxonomy — every extraction run classifies against
    # exactly this list, never a subset, so aggregates stay comparable.
    # Reduced from an original 22 (Gameplay, Immersion, Production Quality,
    # Teardown, Player Count dropped) after reviewing each aspect against
    # "does knowing community consensus on this actually help a user," not
    # just "can a classifier score it" — checked against real mention
    # frequency in the corpus, not just judgment: Teardown had 2 mentions
    # across the entire eligible corpus vs. Setup's 50; Immersion had 6 vs.
    # Theme's 294 (reviewers don't distinguish "good theme" from "felt
    # immersed" — it's the same comment); Gameplay was too broad to add
    # information beyond Mechanics+Strategy+Balance+Player Interaction
    # combined; Production Quality was a vaguer umbrella over the more
    # specific, more-discussed Components/Artwork; Player Count is the
    # wrong shape for a single sentiment score ("great at 2, bad at 5" isn't
    # one verdict) and is redundant with the structured suggested_num_players
    # poll data already shown elsewhere on the game page. See
    # docs/ml/model-cards/absa-deberta.md for the full per-aspect rationale.
    TAXONOMY = [
        "Mechanics", "Strategy", "Theme", "Replayability", "Components", "Artwork",
        "Rulebook", "Setup", "Learning Curve", "Complexity", "Downtime",
        "Player Interaction", "Balance", "Luck", "Solo Play", "Game Length", "Value",
    ]
    # Aspects are classified in chunks of this size per review to bound peak
    # GPU/MPS memory — set to len(TAXONOMY) so all aspects run in one forward
    # pass. Measured against the real deberta-v3-base checkpoint (at the
    # time, with the original 22-aspect taxonomy): batch_size=11 (the old
    # default, tuned for the larger checkpoint) ran at 9.66 rev/sec; 22 (all
    # aspects in one pass) hit 12.04 rev/sec (~20% faster) with no further
    # gain at 44/88, since the taxonomy size is already the max useful batch
    # — there's nothing more to batch once every aspect is in one pass.
    # Batching *across different reviews* was also tested and found to be
    # actively worse (10.18h -> 58.14h projected at batch=16 reviews), since
    # padding pads every sequence in a batch to the longest one present —
    # mixing reviews of different lengths wastes compute on short ones.
    BATCH_SIZE = 17
    # Applied at aggregation (absa_aggregate.py), not extraction --
    # review_aspects stores every winning prediction (positive/negative/
    # neutral) regardless of confidence, so this threshold is a query-time
    # decision, freely revisable without re-running classification. Rows of
    # all three sentiments clearing this confidence bar count toward
    # game_aspect_aggregates -- the same "is the model confident enough to
    # say so" standard applies regardless of which label it landed on.
    # Chosen from a real probe (n=126 evidence-matched pairs, 400-review
    # sample): median winner confidence was 0.991 for positive, 0.968 for
    # negative, 0.843 for neutral -- the model rarely lands in a genuinely
    # ambiguous 3-way split. At 0.5 (the old value), 100% of already-stored
    # pos/neg predictions already cleared it -- effectively no filter at
    # all. At 0.7, 81.7% of that same evidence survives; at 0.9, 71.4%.
    # 0.7 is a starting point, not a final calibration -- the sample is
    # small (only 15 negative/15 neutral pairs) and worth revisiting once
    # the full corpus is classified.
    WINNER_PROB_THRESHOLD = 0.7

    # Reviews-section card state (AspectService, GameDetail.tsx): an aspect
    # reads as confidently Positive/Negative only if that share of mentions
    # clears this bar; otherwise the card falls back to a Mixed/Neutral
    # state. This catches the case plain plurality-of-three misses -- e.g.
    # 45% positive / 10% neutral / 45% negative has a technical positive
    # "winner" by a hair, but that's a genuinely split aspect, not a
    # positive one. Because crossing this bar for positive or negative
    # mathematically guarantees that bucket is also the largest of the
    # three (the other two must share the remainder), there's no conflict
    # with also using "largest bucket" to pick the displayed percentage and
    # evidence quote -- see AspectService.get_game_aspects() and the
    # CommunityConsensus card logic in GameDetail.tsx, which must stay in
    # sync with this value (TypeScript can't import this module directly).
    CARD_DOMINANCE_THRESHOLD = 0.6

    # Minimum total_mentions for an aspect to surface as a card in the
    # reviews-section UI (AspectService.get_game_aspects). A separate knob
    # from SummarizationConfig.MIN_ASPECT_MENTIONS below — same value today,
    # but they gate different decisions (show a card vs. feed the LLM
    # summarizer) and are free to diverge.
    MIN_MENTIONS_FOR_DISPLAY = 5

    # --- Review quality/eligibility filter (app.core.review_quality) ---
    # Purpose: shrink the review pool *before* the expensive DeBERTa step,
    # not classify text quality in the abstract — every signal here is a
    # deterministic hash/count/ratio, no model inference, no training, cheap
    # enough to run over the full ~4.2M-review corpus. See
    # docs/ml/model-cards/absa-deberta.md for the full design rationale.

    # Language gate — reuses reviews.language/language_confidence (already
    # computed by scripts/detect_languages.py) instead of recomputing fastText
    # inference per call, which the old compute_quality_score() did.
    QUALITY_MIN_LANGUAGE_CONFIDENCE = 0.5

    # Hard gates — binary pass/fail, categorically unusable text. Run first
    # since they're the cheapest check and eliminate the most obvious
    # garbage before any pricier per-review computation runs.
    QUALITY_MIN_CHARS = 10
    QUALITY_MIN_TOKENS = 3
    # Reject text where 10%+ of characters are control/unassigned/
    # private-use/surrogate code points — a cheap proxy for corrupted
    # encoding or garbage byte sequences.
    QUALITY_MAX_BAD_UNICODE_RATIO = 0.1

    # SimHash near-duplicate detection — 64-bit fingerprint, Hamming distance
    # <= this many bits counts as a near-duplicate. 3/64 is a conventional
    # starting point for near-dup web text (used e.g. in Google's original
    # SimHash near-duplicate detection); not tuned against this corpus yet.
    QUALITY_SIMHASH_BITS = 64
    QUALITY_SIMHASH_MAX_DISTANCE = 3

    # Weighted combination of the four continuous signals (information
    # density, lexical diversity, domain specificity, boilerplate penalty)
    # into one final score. Starting weights, not yet empirically tuned —
    # scripts/build_review_quality_vocab.py reports the real score
    # distribution on this corpus so the threshold below can be set from
    # measured percentiles rather than guessed.
    QUALITY_DENSITY_WEIGHT = 0.35
    QUALITY_DIVERSITY_WEIGHT = 0.25
    QUALITY_SPECIFICITY_WEIGHT = 0.30
    QUALITY_SPECIFICITY_SCALE = 3.0  # domain-term hit rate is naturally small; scale up before capping at 1.0
    QUALITY_BOILERPLATE_WEIGHT = 0.30
    # Calibrated against a real 50K-review sample (any language, to see
    # true gate attrition): after language + hard filters, scores were
    # p10=0.326 p25=0.373 p50=0.431 p75=0.511 p90=0.604. 0.6 sits at
    # roughly the 90th percentile — deliberately selective per an explicit
    # "don't mind a higher threshold" preference. Measured against the full
    # corpus (scripts/filter_eligible_reviews.py): ~378K/4.2M reviews pass
    # (~9%) — every review that clears this bar is used for ABSA, not
    # capped or further sampled down.
    QUALITY_SCORE_THRESHOLD = 0.6

    # Domain vocabulary for the specificity signal. Derived from the top 300
    # most frequent non-stopword (stemmed) terms across a 200K-review sample
    # (scripts/build_review_quality_vocab.py -> data/review_quality_vocab_candidates.txt),
    # then hand-curated: raw frequency surfaces generic praise/discourse
    # words ("game", "play", "fun", "good", "great", "like", "think", "way")
    # ahead of specific ones, so those were dropped and only genuinely
    # game-specific/content-bearing terms (mechanics, components, genres,
    # terms matching the ABSA aspect taxonomy) were kept. Stored as stems
    # (NLTK SnowballStemmer) — scoring stems review tokens the same way
    # before checking membership, so "component"/"components" both match.
    DOMAIN_VOCABULARY = {
        "card", "rule", "mechan", "theme", "turn", "board", "strategi", "strateg",
        "dice", "die", "luck", "score", "expans", "action", "win", "tile", "design",
        "roll", "deck", "decis", "compon", "light", "round", "collect", "gameplay",
        "solo", "famili", "box", "edit", "hand", "interact", "tabl", "draw", "art",
        "artwork", "placement", "worker", "balanc", "power", "complex", "filler",
        "replay", "oppon", "resourc", "space", "piec", "tactic", "manag", "race",
        "charact", "trade", "teach", "map", "color", "parti", "puzzl", "war", "area",
        "abstract", "euro", "scenario", "difficult", "classic", "battl", "victori",
        "qualiti", "track", "draft", "combat", "themat", "money", "abil", "stori",
        "combin", "engin", "auction", "citi", "bid", "push", "trick", "token",
        "setup", "multipl", "attack", "tension", "kickstart", "campaign", "role",
        "explor", "cooper",
    }

    # Boilerplate n-grams — corpus-derived (same script), applied by raw
    # frequency threshold with no human curation step: an n-gram repeated
    # across hundreds of *different* reviews is unambiguously templated
    # filler regardless of judgment calls, unlike single-word vocabulary.
    BOILERPLATE_NGRAM_SIZE = 4
    BOILERPLATE_MIN_COUNT = 50

    # fastText language-ID model — pinned external download, not a trained
    # artifact, so it's tracked here by URL/filename rather than in MLflow.
    # Used by scripts/detect_languages.py (produces reviews.language/
    # language_confidence) and the superseded scripts/absa_filter.py pilot
    # path — no longer used by the canonical filtering pipeline, which reads
    # the precomputed columns instead of running fastText itself.
    FASTTEXT_MODEL_URL = "https://dl.fbaipublicfiles.com/fasttext/supervised-models/lid.176.ftz"
    FASTTEXT_MODEL_FILENAME = "lid.176.ftz"


class SummarizationConfig:
    """LLM-generated "Customers say" per-game summaries."""

    MIN_REVIEWS_FOR_ABSA = 15
    MIN_ASPECT_MENTIONS = 5
    TOP_K_ASPECTS = 5
    MAX_REVIEWS_PER_ASPECT = 100
    TEMPERATURE = 0.0
    MAX_TOKENS = 2048
    # Real, measured, non-deterministic failure mode despite temperature=0:
    # the local MLX server occasionally returns an empty completion (no
    # content, finish_reason=stop, well under MAX_TOKENS) for a prompt that
    # succeeds on retry with byte-identical input -- reproduced directly
    # against Ark Nova's Theme aspect (46 real evidence lines), not a
    # synthetic worst case. Without a retry, one flaky call would abort an
    # entire batch run partway through. 2 retries, not indefinite -- a
    # genuinely broken prompt/schema should still surface as an error.
    MAX_LLM_RETRIES = 2


class RecommenderConfig:
    """Popularity, content-based, collaborative, and hybrid recommenders.

    Paradigms: popularity, content, collaborative, hybrid. Graph-based
    models (graph_jaccard, deepwalk) live inside the content paradigm --
    they use game metadata (mechanics/categories/designers/...) as their
    similarity substrate, same as the other content models, just via graph
    structure instead of vector similarity.
    """

    # --- Collaborative filtering (real fit() steps) ---
    CF_ITEM_COSINE_MIN_SHARED_USERS = 50
    CF_ALS_FACTORS = 50
    CF_ALS_ITERATIONS = 15
    CF_ALS_REGULARIZATION = 0.1
    # implicit.als.AlternatingLeastSquares expects a confidence-weighted
    # matrix (Hu/Koren/Volinsky 2008: confidence = 1 + alpha*r), not raw
    # preference values -- feeding it raw 1-10 ratings directly as
    # confidence (the previous behavior) conflates "how confident are we
    # this interaction is positive" with the rating's own polarity, so a
    # rating of 2/10 got read as a weak-but-positive signal instead of a
    # dislike. alpha=40 is the paper's own default; not tuned against this
    # dataset specifically.
    CF_ALS_CONFIDENCE_ALPHA = 40

    # --- Content-based (similarity only, no fit step) ---
    # metadata = 0.7 * category/mechanic TF-IDF sim + 0.3 * numeric-feature sim
    METADATA_CATEGORICAL_WEIGHT = 0.7
    METADATA_NUMERIC_WEIGHT = 0.3
    TFIDF_MAX_FEATURES = 10000
    RECS_PER_MODEL_LIMIT = 10

    # --- Graph-based (part of the content paradigm — see class docstring) ---
    # subdomains/families added alongside mechanics/categories -- previously
    # missing from every content model except embedding. "themes" is
    # deliberately NOT its own relation here: BGG's Theme: namespace is
    # already one of families' 72 namespaces (see build_master_dataset.py),
    # so adding both would double-count the same tags. Renormalized by
    # run_jaccard (divides by the sum), so these don't need to sum to 1.
    # Relative weights are a disclosed starting point, not tuned yet.
    GRAPH_JACCARD_WEIGHTS = {
        "mechanics": 0.35, "categories": 0.25, "subdomains": 0.15, "families": 0.1,
        "designers": 0.05, "publishers": 0.025, "artists": 0.025,
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

    # --- Hybrid (cross-paradigm combiner, model id: "hybrid") ---
    # Combines one representative collaborative model's score with one
    # representative content model's score -- not a recursive/arbitrary
    # composition, one fixed formula: 0.5*collaborative + 0.5*content.
    # Computed live at request time (RecommendationService.get_recommendations),
    # not precomputed/stored: both inputs are already-precomputed top-N
    # lists, so combining them is a few dozen floats and a sort, not an
    # O(n^2) similarity matrix -- the same "cheap and freshness-sensitive
    # stays live" reasoning already applied to the "embedding" model in that
    # same method. An even 0.5/0.5 split is a disclosed starting point, not
    # tuned against any evaluation yet.
    HYBRID_ENGINE_WEIGHTS = {"collaborative": 0.5, "content": 0.5}
    # Cheapest model per paradigm (no iterative fit / no embedding-model
    # dependency), per the explicit "don't train everything, pick the
    # cheapest representative" direction this was designed under. Both
    # swappable later without changing the blending logic itself.
    HYBRID_COLLABORATIVE_MODEL = "cf_item_cosine"
    HYBRID_CONTENT_MODEL = "metadata"


# Single source of truth for "what recommendation models exist" -- serves
# GET /api/recommendation-models (RecommendationService.get_recommendation_models()),
# which the frontend reads instead of hardcoding its own separate list.
# 9 models across 4 paradigms, each paradigm classified by what data the
# model actually consumes, not by algorithm family alone -- graph_jaccard
# and deepwalk sit under content because both build their graph purely from
# item metadata (mechanics/categories/designers/publishers/artists) and
# never read the ratings table, even though "graph" might suggest
# collaborative at a glance. Superseded a 3-entry backend method nobody
# called and a disagreeing 10-entry hardcoded frontend array.
RECOMMENDATION_MODELS = [
    {"id": "popularity", "paradigm": "popularity", "name": "Popularity Ranking",
     "description": "Universally popular, highly-ranked games. No personalization, no per-game computation."},
    {"id": "metadata", "paradigm": "content", "name": "Metadata Similarity",
     "description": "Cosine similarity over category/mechanic/subdomain/family and numeric (weight, playtime, player count) features."},
    {"id": "tfidf", "paradigm": "content", "name": "TF-IDF Similarity",
     "description": "Cosine similarity over TF-IDF-vectorized name, description, categories, mechanics, subdomains, families, designers, and publishers."},
    {"id": "embedding", "paradigm": "content", "name": "Semantic Embedding Similarity",
     "description": "Live pgvector nearest-neighbor search over Qwen3-Embedding-0.6B vectors -- the only content model computed at request time, not precomputed."},
    {"id": "graph_jaccard", "paradigm": "content", "name": "Graph Jaccard",
     "description": "Weighted Jaccard set-overlap across mechanics, categories, subdomains, families, designers, publishers, and artists -- item-metadata graph, not a user-item interaction graph."},
    {"id": "deepwalk", "paradigm": "content", "name": "Graph Embedding (DeepWalk)",
     "description": "DeepWalk graph embedding (random walks + Word2Vec) over the same item-metadata graph as Graph Jaccard."},
    {"id": "cf_item_cosine", "paradigm": "collaborative", "name": "Item-Item Similarity",
     "description": "Cosine similarity over the item-item co-occurrence matrix from real user ratings, masked below a minimum shared-rater threshold."},
    {"id": "cf_als", "paradigm": "collaborative", "name": "Matrix Factorization (ALS)",
     "description": "Alternating Least Squares over user ratings (confidence-weighted per Hu/Koren/Volinsky); item similarity in the resulting latent factor space."},
    {"id": "hybrid", "paradigm": "hybrid", "name": "Weighted Hybrid",
     "description": "Blends one collaborative and one content model's scores 0.5/0.5, computed live per request -- the only model that combines across paradigms rather than within one."},
]


class AssistantConfig:
    """LLM-powered natural-language query intent parsing."""

    TEMPERATURE = 0.0
    MAX_TOKENS = 4096
