
from sqlalchemy import text
from app.database.session import SessionLocal

def update_lexical_search_vectors():
    print("Connecting to database...")
    db = SessionLocal()
    
    # Weight A: Name
    # Weight B: Themes, Mechanics, Categories, Subdomains, Families — every
    #   structured taxonomy tag, all in one tier. Subdomains/Families were
    #   missing from this tsvector entirely until now (a real gap: both are
    #   used everywhere else — filters, the embedding document — but were
    #   never indexed for lexical search, so a query for a subdomain name
    #   like "party game" or a family name matched nothing on that basis).
    # Weight C: Description — free text; useful for phrase/unique-word
    #   matches, but also the main source of incidental noise (a long,
    #   flavor-text-heavy description is more likely to contain a query's
    #   words by coincidence, unrelated to what the game is actually about
    #   — see docs/ml/model-cards/search-lexical.md for a concrete example).
    #   Deliberately still below the structured tags in weight, not removed.
    # Weight D: Designers, Artists, Publishers

    sql = """
    UPDATE games g
    SET search_vector =
        setweight(to_tsvector('english_unaccent', coalesce(g.name, '')), 'A') ||
        setweight(to_tsvector('english_unaccent', coalesce((
            SELECT string_agg(t.name, ' ') FROM game_themes gt JOIN themes t ON gt.theme_id = t.id WHERE gt.game_id = g.bgg_id
        ), '') || ' ' || coalesce((
            SELECT string_agg(m.name, ' ') FROM game_mechanics gm JOIN mechanics m ON gm.mechanic_id = m.id WHERE gm.game_id = g.bgg_id
        ), '') || ' ' || coalesce((
            SELECT string_agg(c.name, ' ') FROM game_categories gc JOIN categories c ON gc.category_id = c.id WHERE gc.game_id = g.bgg_id
        ), '') || ' ' || coalesce((
            SELECT string_agg(s.name, ' ') FROM game_subdomains gs JOIN subdomains s ON gs.subdomain_id = s.id WHERE gs.game_id = g.bgg_id
        ), '') || ' ' || coalesce((
            SELECT string_agg(sf.name, ' ') FROM game_subfamilies gsf JOIN subfamilies sf ON gsf.subfamily_id = sf.id WHERE gsf.game_id = g.bgg_id
        ), '')), 'B') ||
        setweight(to_tsvector('english_unaccent', coalesce(g.description, '')), 'C') ||
        setweight(to_tsvector('english_unaccent', coalesce((
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
