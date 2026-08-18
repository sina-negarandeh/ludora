import mlflow
from sqlalchemy import text, func
from sqlalchemy.dialects.postgresql import insert
from app.database.session import SessionLocal
from app.database.models import GameEmbedding
from app.core.ml_config import SearchConfig
from app.core.mlflow_utils import tracked_run
from app.core import embeddings as embedding_model

def bucket_label(value, buckets):
    """Map a numeric value to its bucket's text phrase (SearchConfig.WEIGHT_BUCKETS /
    PLAYTIME_BUCKETS) — converts a raw number into the same descriptive vocabulary
    the frontend's own filter presets use, since embedding models represent
    phrases like "heavy strategy game" far better than a raw float or int.
    """
    if value is None:
        return None
    last = len(buckets) - 1
    for i, (low, high, phrase) in enumerate(buckets):
        # Every bucket's upper bound is exclusive except the very last one,
        # which is inclusive — otherwise a value sitting exactly on the top
        # of the whole range (e.g. game_weight == 5.0, the max on BGG's
        # 1-5 scale) would match no bucket at all.
        upper_ok = high is None or value < high or (i == last and value == high)
        if value >= low and upper_ok:
            return phrase
    return None

def build_structured_document(game_name, description, themes, mechanics, categories,
                               subdomains, families, game_weight, mfg_playtime):
    doc_parts = []

    if game_name:
        doc_parts.append(f"Name: {game_name}")

    if description:
        doc_parts.append(f"Description:\n{description[:SearchConfig.DESCRIPTION_TRUNCATE_CHARS]}")

    if themes:
        doc_parts.append("Themes:\n" + "\n".join(themes))

    if mechanics:
        doc_parts.append("Mechanics:\n" + "\n".join(mechanics))

    if categories:
        doc_parts.append("Categories:\n" + "\n".join(categories))

    if subdomains:
        doc_parts.append("Type:\n" + "\n".join(subdomains))

    if families:
        doc_parts.append("Families:\n" + "\n".join(families))

    # Bucketed numeric descriptors — designers/artists/publishers are
    # deliberately excluded (lexical search already handles proper-noun
    # matches at the D-weight tier; adding them here would only dilute the
    # thematic signal from the fields above, not add retrieval capability).
    weight_phrase = bucket_label(game_weight, SearchConfig.WEIGHT_BUCKETS)
    playtime_phrase = bucket_label(mfg_playtime, SearchConfig.PLAYTIME_BUCKETS)
    experience_parts = [p for p in (weight_phrase, playtime_phrase) if p]
    if experience_parts:
        doc_parts.append("Experience:\n" + "\n".join(experience_parts))

    return "\n\n".join(doc_parts)

def update_embeddings():
    print(f"Loading embedding model ({SearchConfig.EMBEDDING_MODEL})...")
    model_name = SearchConfig.EMBEDDING_MODEL

    db = SessionLocal()

    # Query to fetch games and their relevant metadata.
    # Designers, artists, and publishers are deliberately omitted — lexical
    # search already covers proper-noun matches (search_vector's D-tier).
    query = """
        SELECT
            g.bgg_id,
            g.name,
            g.description,
            g.game_weight,
            g.mfg_playtime,
            (SELECT array_agg(t.name) FROM game_themes gt JOIN themes t ON gt.theme_id = t.id WHERE gt.game_id = g.bgg_id) as themes,
            (SELECT array_agg(m.name) FROM game_mechanics gm JOIN mechanics m ON gm.mechanic_id = m.id WHERE gm.game_id = g.bgg_id) as mechanics,
            (SELECT array_agg(c.name) FROM game_categories gc JOIN categories c ON gc.category_id = c.id WHERE gc.game_id = g.bgg_id) as categories,
            (SELECT array_agg(s.name) FROM game_subdomains gs JOIN subdomains s ON gs.subdomain_id = s.id WHERE gs.game_id = g.bgg_id) as subdomains,
            (SELECT array_agg(sf.name) FROM game_subfamilies gsf JOIN subfamilies sf ON gsf.subfamily_id = sf.id WHERE gsf.game_id = g.bgg_id) as families
        FROM games g
    """

    print("Fetching games from database...")
    games = db.execute(text(query)).fetchall()
    print(f"Loaded {len(games)} games to process.")

    mlflow.log_params({
        "embedding_model": SearchConfig.EMBEDDING_MODEL,
        "description_truncate_chars": SearchConfig.DESCRIPTION_TRUNCATE_CHARS,
        "embed_max_tokens": SearchConfig.EMBED_MAX_TOKENS,
        "embed_batch_size": SearchConfig.EMBED_BATCH_SIZE,
        "n_games": len(games),
    })

    print("Building documents...")
    items = []  # (bgg_id, document) pairs
    for row in games:
        doc = build_structured_document(
            row.name,
            row.description,
            row.themes or [],
            row.mechanics or [],
            row.categories or [],
            row.subdomains or [],
            row.families or [],
            row.game_weight,
            row.mfg_playtime,
        )
        items.append((row.bgg_id, doc))

    # Sort by document length before batching — batch_encode_plus pads every
    # item in a batch up to that batch's longest member, so pulling games in
    # raw DB order means one long outlier inflates its entire batch's cost
    # for no quality benefit. Sorting first makes each batch length-uniform,
    # which measured ~2x faster on this catalog with identical output
    # (same documents, same model, just reordered).
    items.sort(key=lambda pair: len(pair[1]))

    # We will process in batches to save memory and commit efficiently
    batch_size = SearchConfig.EMBED_BATCH_SIZE
    total_processed = 0

    for i in range(0, len(items), batch_size):
        batch = items[i:i+batch_size]
        bgg_ids = [bgg_id for bgg_id, _ in batch]
        documents = [doc for _, doc in batch]

        print(f"Encoding batch {i//batch_size + 1}/{(len(items) + batch_size - 1)//batch_size}...")
        embeddings = embedding_model.encode(documents, is_query=False)

        # Upsert into game_embeddings — one row per (game, model), so a
        # rerun of a *different* model doesn't touch or lose this one's rows.
        rows = [
            {
                "game_id": bgg_ids[idx],
                "model": model_name,
                "dimension": len(emb),
                "embedding": emb,
            }
            for idx, emb in enumerate(embeddings)
        ]
        stmt = insert(GameEmbedding).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=["game_id", "model"],
            set_={
                "dimension": stmt.excluded.dimension,
                "embedding": stmt.excluded.embedding,
                "created_at": func.now(),
            },
        )
        db.execute(stmt)
        db.commit()
        
        total_processed += len(batch)
        print(f"Saved {total_processed} / {len(games)} embeddings.")

    mlflow.log_metrics({"games_processed": total_processed})
    print("Embedding update complete!")

if __name__ == "__main__":
    with tracked_run("search/embedding_build", run_name="update_embeddings"):
        update_embeddings()
