import sys
from pathlib import Path

# Add backend dir to path so we can import app modules
sys.path.append(str(Path(__file__).parent.parent.resolve()))

from sqlalchemy import text
from app.database.session import SessionLocal

def update_lexical_search_vectors():
    print("Connecting to database...")
    db = SessionLocal()
    
    # Weight A: Name
    # Weight B: Themes, Mechanics, Categories
    # Weight C: Description
    # Weight D: Designers, Artists, Publishers
    
    sql = """
    UPDATE games g
    SET search_vector = 
        setweight(to_tsvector('english', coalesce(g.name, '')), 'A') ||
        setweight(to_tsvector('english', coalesce((
            SELECT string_agg(t.name, ' ') FROM game_themes gt JOIN themes t ON gt.theme_id = t.id WHERE gt.game_id = g.bgg_id
        ), '') || ' ' || coalesce((
            SELECT string_agg(m.name, ' ') FROM game_mechanics gm JOIN mechanics m ON gm.mechanic_id = m.id WHERE gm.game_id = g.bgg_id
        ), '') || ' ' || coalesce((
            SELECT string_agg(c.name, ' ') FROM game_categories gc JOIN categories c ON gc.category_id = c.id WHERE gc.game_id = g.bgg_id
        ), '')), 'B') ||
        setweight(to_tsvector('english', coalesce(g.description, '')), 'C') ||
        setweight(to_tsvector('english', coalesce((
            SELECT string_agg(d.name, ' ') FROM game_designers gd JOIN designers d ON gd.designer_id = d.id WHERE gd.game_id = g.bgg_id
        ), '') || ' ' || coalesce((
            SELECT string_agg(a.name, ' ') FROM game_artists ga JOIN artists a ON ga.artist_id = a.id WHERE ga.game_id = g.bgg_id
        ), '') || ' ' || coalesce((
            SELECT string_agg(p.name, ' ') FROM game_publishers gp JOIN publishers p ON gp.publisher_id = p.id WHERE gp.game_id = g.bgg_id
        ), '')), 'D');
    """
    
    print("Executing massive UPDATE to regenerate search_vector for all games...")
    result = db.execute(text(sql))
    db.commit()
    print(f"Updated search vectors successfully. Rows affected: {result.rowcount}")
    
if __name__ == "__main__":
    update_lexical_search_vectors()
