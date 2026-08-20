"""Shared MLX embedding model loader/encoder.

Both SearchService (live query encoding) and scripts/update_embeddings.py
(offline document encoding) need to load and run the same configured model
the same way — this is the one place that does it, so the two call sites
can't drift on load args, instruction-prefix handling, or tokenization.

Loads once per process (module-level cache), consistent with how the
previous SentenceTransformer was loaded once at import time.
"""

from mlx_embeddings.utils import load as _mlx_load

from app.core.ml_config import SearchConfig

_model = None
_tokenizer = None


def _get_model():
    global _model, _tokenizer
    if _model is None:
        _model, _tokenizer = _mlx_load(SearchConfig.EMBEDDING_MODEL)
    # Narrows the return type past the module-level None default -- by
    # this point the load above has always run, whether just now or on
    # an earlier call.
    assert _model is not None and _tokenizer is not None
    return _model, _tokenizer


def encode(texts: list[str], is_query: bool = False) -> list[list[float]]:
    """Encode a batch of texts to L2-normalized embedding vectors.

    `is_query=True` applies SearchConfig.QUERY_INSTRUCTION — the asymmetric
    instruction prefix instruction-aware models (e.g. Qwen3-Embedding) expect
    on the query side only — but only when the configured model is actually
    in SearchConfig.INSTRUCTION_AWARE_MODELS. Documents are always encoded
    plain, regardless of this flag.
    """
    model, tokenizer = _get_model()

    if is_query and SearchConfig.EMBEDDING_MODEL in SearchConfig.INSTRUCTION_AWARE_MODELS:
        texts = [SearchConfig.QUERY_INSTRUCTION.format(query=t) for t in texts]

    inputs = tokenizer.batch_encode_plus(
        texts,
        return_tensors="mlx",
        padding=True,
        truncation=True,
        max_length=SearchConfig.EMBED_MAX_TOKENS,
    )
    outputs = model(inputs["input_ids"], attention_mask=inputs["attention_mask"])
    return outputs.text_embeds.tolist()
