import os
import time
import argparse
import requests
import fasttext

from sqlalchemy import text
from app.database.session import engine

def download_fasttext_model(model_path):
    if os.path.exists(model_path):
        return
    print("Downloading fastText language model...")
    url = "https://dl.fbaipublicfiles.com/fasttext/supervised-models/lid.176.ftz"
    r = requests.get(url, allow_redirects=True)
    r.raise_for_status()
    # Write to a temp file first and rename atomically, so a failed/interrupted
    # download can never leave a truncated file that a later run mistakes for
    # "already downloaded" and silently loads as if it were valid.
    tmp_path = model_path + ".tmp"
    with open(tmp_path, 'wb') as f:
        f.write(r.content)
    os.replace(tmp_path, model_path)
    print("Downloaded.")

def detect_language(ft_model, text_str):
    """Returns (language, confidence). 'unknown'/None means there was no
    usable text to classify — distinct from a real, low-confidence guess,
    which is still returned as-is so callers can threshold on `confidence`
    themselves rather than have the pipeline throw the guess away.
    """
    if not isinstance(text_str, str) or not text_str.strip():
        return 'unknown', None
    clean_text = text_str.replace('\n', ' ')
    langs, probs = ft_model.predict(clean_text, k=1)
    lang_code = langs[0].replace('__label__', '')[:10]
    return lang_code, float(probs[0])

def run(limit=None):
    model_path = os.path.join(os.path.dirname(__file__), '../data/models/lid.176.ftz')
    download_fasttext_model(model_path)
    print("Loading fasttext model...")
    ft_model = fasttext.load_model(model_path)

    batch_size = 10000
    total_processed = 0
    total_failed = 0
    start_time = time.time()

    with engine.begin() as conn:
        print("Checking for rows to update...")
        count_res = conn.execute(text("SELECT COUNT(id) FROM reviews WHERE language IS NULL"))
        total_remaining = count_res.scalar()
        if limit:
            total_remaining = min(total_remaining, limit)

        print(f"Found {total_remaining} reviews without a language.")
        if total_remaining == 0:
            print("Done.")
            return

    while True:
        with engine.connect() as conn:
            # Fetch a batch
            query = "SELECT id, comment FROM reviews WHERE language IS NULL"
            if limit:
                fetch_limit = min(batch_size, limit - total_processed)
            else:
                fetch_limit = batch_size

            if fetch_limit <= 0:
                break

            query += f" LIMIT {fetch_limit}"

            result = conn.execute(text(query))
            rows = result.fetchall()

            if not rows:
                break

            # Process batch — a single row's prediction failing (e.g. malformed
            # text) must not crash the whole batch and leave that row NULL
            # forever, permanently re-blocking every future run on it.
            updates = []
            for row in rows:
                try:
                    lang, confidence = detect_language(ft_model, row.comment)
                except Exception as e:
                    print(f"  Row {row.id} failed language detection ({e}); marking unknown.")
                    lang, confidence = 'unknown', None
                    total_failed += 1
                updates.append({"b_id": row.id, "b_lang": lang, "b_conf": confidence})

            # Bulk update
            if updates:
                conn.execute(
                    text("UPDATE reviews SET language = :b_lang, language_confidence = :b_conf WHERE id = :b_id"),
                    updates
                )
                conn.commit()

            total_processed += len(rows)
            elapsed = time.time() - start_time
            rate = total_processed / elapsed if elapsed > 0 else 0
            print(f"Processed {total_processed} rows (Rate: {rate:.2f} rows/sec)...")

            if limit and total_processed >= limit:
                break

    total_time = time.time() - start_time
    print(f"Complete. Processed {total_processed} rows ({total_failed} failed detection) in {total_time:.2f} seconds.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="Limit number of rows to process")
    args = parser.parse_args()
    run(limit=args.limit)
