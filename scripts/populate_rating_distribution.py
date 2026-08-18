import json
import psycopg
import time

from app.core.config import settings

def main():
    print(f"[{time.strftime('%X')}] Connecting to database...")
    db_url = settings.DATABASE_URL.replace('postgresql+psycopg://', 'postgresql://')
    
    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            print(f"[{time.strftime('%X')}] Aggregating 26M ratings into distributions...")
            # PostgreSQL query to bucket ratings into 0.5 increments (1.0 to 10.0)
            cur.execute("""
                SELECT 
                    game_id, 
                    GREATEST(1.0, ROUND(rating * 2) / 2.0) as bucket, 
                    COUNT(*) as cnt
                FROM ratings
                GROUP BY 1, 2
                ORDER BY 1, 2;
            """)
            
            distributions = {}
            for row in cur.fetchall():
                game_id = row[0]
                bucket = float(row[1])
                cnt = row[2]
                
                if game_id not in distributions:
                    # Initialize 19 buckets (1.0, 1.5, 2.0, ..., 10.0)
                    distributions[game_id] = {x / 2.0: 0 for x in range(2, 21)}
                
                # Make sure bucket is within 1.0 - 10.0
                if bucket > 10.0: bucket = 10.0
                if bucket < 1.0: bucket = 1.0
                
                distributions[game_id][bucket] += cnt
            
            print(f"[{time.strftime('%X')}] Updating {len(distributions)} games in database...")
            
            # Prepare updates
            updates = []
            for game_id, dist_dict in distributions.items():
                # Extract counts in order of buckets (1.0, 1.5 ... 10.0)
                dist_list = [dist_dict[x / 2.0] for x in range(2, 21)]
                # Number of ratings is the sum of all counts
                total_ratings = sum(dist_list)
                
                updates.append((json.dumps(dist_list), total_ratings, game_id))
            
            # Execute batch update
            # Using execute_batch or executemany
            cur.executemany("""
                UPDATE games 
                SET rating_distribution = CAST(%s AS json), num_ratings = %s
                WHERE bgg_id = %s
            """, updates)
            
            conn.commit()
            print(f"[{time.strftime('%X')}] Successfully updated rating distributions!")

if __name__ == "__main__":
    main()
