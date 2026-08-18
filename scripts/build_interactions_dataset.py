import pandas as pd
import os
import csv

RAW_DATA_JVANELTEREN_DIR = os.environ.get(
    'RAW_DATA_JVANELTEREN_DIR',
    'data/raw/kaggle_datasets_jvanelteren_boardgamegeek-reviews',
)
PROCESSED_DATA_DIR = os.environ.get('PROCESSED_DATA_DIR', 'data/processed')


def main():
    input_file = os.path.join(RAW_DATA_JVANELTEREN_DIR, 'bgg-26m-reviews.csv')
    ratings_out = os.path.join(PROCESSED_DATA_DIR, 'master_ratings.csv')
    reviews_out = os.path.join(PROCESSED_DATA_DIR, 'master_reviews.csv')
    users_out = os.path.join(PROCESSED_DATA_DIR, 'master_users.csv')

    # Make sure processed dir exists
    os.makedirs(PROCESSED_DATA_DIR, exist_ok=True)

    # Clean existing outputs
    for f in [ratings_out, reviews_out, users_out]:
        if os.path.exists(f):
            os.remove(f)

    user_to_id = {}
    next_user_id = 1
    seen_pairs = set()

    chunk_size = 1000000
    total_processed = 0
    duplicates_skipped = 0

    print("Building interactions dataset in chunks...")

    # Write headers
    with open(ratings_out, 'w') as f:
        f.write('user_id,game_id,rating\n')
        
    with open(reviews_out, 'w') as f:
        writer = csv.writer(f)
        writer.writerow(['user_id', 'game_id', 'rating', 'comment'])

    # Open files for appending
    f_rat = open(ratings_out, 'a', newline='')
    f_rev = open(reviews_out, 'a', newline='')
    writer_rat = csv.writer(f_rat)
    writer_rev = csv.writer(f_rev)

    try:
        for chunk in pd.read_csv(input_file, chunksize=chunk_size):
            # Drop malformed rows
            chunk = chunk.dropna(subset=['user', 'ID'])
            
            # Prepare to write chunk row by row to allow deterministic deduplication
            for row in chunk.itertuples():
                u = str(row.user).strip()
                g_id = int(row.ID)
                r = row.rating
                c = row.comment
                
                # Deduplication Policy: Keep the First Encountered Record
                pair = (u, g_id)
                if pair in seen_pairs:
                    duplicates_skipped += 1
                    continue
                seen_pairs.add(pair)
                
                # Map User
                if u not in user_to_id:
                    user_to_id[u] = next_user_id
                    next_user_id += 1
                u_id = user_to_id[u]
                
                # Write to Ratings (every interaction)
                writer_rat.writerow([u_id, g_id, r])
                
                # Write to Reviews (only if comment exists)
                if pd.notna(c) and str(c).strip():
                    writer_rev.writerow([u_id, g_id, r, str(c).strip()])

            total_processed += len(chunk)
            print(f"Processed {total_processed} raw rows... (Skipped {duplicates_skipped} duplicates)")
    finally:
        f_rat.close()
        f_rev.close()

    print("Writing master users table...")
    users_df = pd.DataFrame({
        'id': list(user_to_id.values()),
        'external_user_id': list(user_to_id.keys())
    })
    users_df.to_csv(users_out, index=False)
    
    print(f"Done! Unique Users: {len(users_df)}")
    print(f"Total Unique Interactions (Ratings): {len(seen_pairs)}")
    print(f"Total Duplicates Deduplicated: {duplicates_skipped}")

if __name__ == "__main__":
    main()
