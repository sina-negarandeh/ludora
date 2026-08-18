from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, DateTime, JSON, Text, func, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import TSVECTOR
from pgvector.sqlalchemy import Vector
from app.database.session import Base

# --- Join Tables ---
class GameCategory(Base):
    __tablename__ = "game_categories"
    game_id = Column(Integer, ForeignKey("games.bgg_id", ondelete="CASCADE"), primary_key=True)
    category_id = Column(Integer, ForeignKey("categories.id", ondelete="CASCADE"), primary_key=True, index=True)

class GameMechanic(Base):
    __tablename__ = "game_mechanics"
    game_id = Column(Integer, ForeignKey("games.bgg_id", ondelete="CASCADE"), primary_key=True)
    mechanic_id = Column(Integer, ForeignKey("mechanics.id", ondelete="CASCADE"), primary_key=True, index=True)

class GameDesigner(Base):
    __tablename__ = "game_designers"
    game_id = Column(Integer, ForeignKey("games.bgg_id", ondelete="CASCADE"), primary_key=True)
    designer_id = Column(Integer, ForeignKey("designers.id", ondelete="CASCADE"), primary_key=True, index=True)

class GamePublisher(Base):
    __tablename__ = "game_publishers"
    game_id = Column(Integer, ForeignKey("games.bgg_id", ondelete="CASCADE"), primary_key=True)
    publisher_id = Column(Integer, ForeignKey("publishers.id", ondelete="CASCADE"), primary_key=True, index=True)

class GameArtist(Base):
    __tablename__ = "game_artists"
    game_id = Column(Integer, ForeignKey("games.bgg_id", ondelete="CASCADE"), primary_key=True)
    artist_id = Column(Integer, ForeignKey("artists.id", ondelete="CASCADE"), primary_key=True, index=True)

class GameTheme(Base):
    __tablename__ = "game_themes"
    game_id = Column(Integer, ForeignKey("games.bgg_id", ondelete="CASCADE"), primary_key=True)
    theme_id = Column(Integer, ForeignKey("themes.id", ondelete="CASCADE"), primary_key=True, index=True)

class GameSubdomain(Base):
    __tablename__ = "game_subdomains"
    game_id = Column(Integer, ForeignKey("games.bgg_id", ondelete="CASCADE"), primary_key=True)
    subdomain_id = Column(Integer, ForeignKey("subdomains.id", ondelete="CASCADE"), primary_key=True, index=True)

class GameSubfamily(Base):
    __tablename__ = "game_subfamilies"
    game_id = Column(Integer, ForeignKey("games.bgg_id", ondelete="CASCADE"), primary_key=True)
    subfamily_id = Column(Integer, ForeignKey("subfamilies.id", ondelete="CASCADE"), primary_key=True, index=True)

# --- Entity Tables ---

class Category(Base):
    """BGG's real Category field (boardgamecategory) — e.g. Adventure,
    Economic, Card Game. Not the old "categories" concept; see Subdomain.
    """
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, index=True, nullable=False)

class Theme(Base):
    """BGG Family's "Theme:" group only (e.g. "Theme: Cthulhu Mythos") —
    distinct from Category. See docs/data/README.md.
    """
    __tablename__ = "themes"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, index=True, nullable=False)

class Subdomain(Base):
    """BGG's rank/leaderboard type (Thematic/Strategy/War/Family/CGS/
    Abstract/Party/Childrens) — this used to be mislabeled "Category".
    """
    __tablename__ = "subdomains"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, index=True, nullable=False)

class Mechanic(Base):
    __tablename__ = "mechanics"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, index=True, nullable=False)

class Family(Base):
    """A BGG Family namespace/group (e.g. "Animals", "Mechanism", "Theme",
    "Crowdfunding") — the full boardgamefamily field, all 72 groups. See
    Subfamily for the specific values within a group, and docs/data/README.md.
    """
    __tablename__ = "families"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, index=True, nullable=False)

class Subfamily(Base):
    """A specific BGG Family value within a group (e.g. "Bears" within
    "Animals"). Includes the Theme: group, which is also separately
    extracted into the themes table today — consolidating the two is a
    later decision.
    """
    __tablename__ = "subfamilies"
    id = Column(Integer, primary_key=True, autoincrement=True)
    family_id = Column(Integer, ForeignKey("families.id", ondelete="CASCADE"), nullable=False, index=True)
    value = Column(String, nullable=False)
    name = Column(String, unique=True, index=True, nullable=False)  # "{family.name}: {value}"

    family = relationship("Family")

class Designer(Base):
    __tablename__ = "designers"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, index=True, nullable=False)

class Publisher(Base):
    __tablename__ = "publishers"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, index=True, nullable=False)

class Artist(Base):
    __tablename__ = "artists"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, index=True, nullable=False)

# --- Core Table ---

class Game(Base):
    __tablename__ = "games"

    bgg_id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    description = Column(Text)
    year_published = Column(Integer)
    game_weight = Column(Float)
    avg_rating = Column(Float)
    median_rating = Column(Float)
    min_players = Column(Integer)
    max_players = Column(Integer)
    mfg_playtime = Column(Integer)
    min_age = Column(Integer)
    image_path = Column(String)
    rank = Column(Integer, nullable=True)
    num_ratings = Column(Integer, nullable=True)
    num_comments = Column(Integer, nullable=True)
    owned_count = Column(Integer, nullable=True)
    trading_count = Column(Integer, nullable=True)
    wanting_count = Column(Integer, nullable=True)
    wishing_count = Column(Integer, nullable=True)
    rating_distribution = Column(JSON, nullable=True)
    subdomain_ranks = Column(JSON, nullable=True)

    # Fields computed by build_master_dataset.py that previously never
    # reached the schema — see docs/architecture/data-pipeline.md.
    min_playtime = Column(Integer, nullable=True)
    max_playtime = Column(Integer, nullable=True)
    bayes_avg_rating = Column(Float, nullable=True)
    stddev_rating = Column(Float, nullable=True)
    num_weight_votes = Column(Integer, nullable=True)
    thumbnail_url = Column(String, nullable=True)
    kickstarted = Column(Boolean, nullable=True)
    is_reimplementation = Column(Boolean, nullable=True)

    # jvanelteren poll data (Best/Recommended/Not Recommended per player
    # count, age votes, language-dependence votes) — replaces the flat,
    # unused Threnjen best_players/good_players/com_age_rec/language_ease.
    suggested_num_players = Column(JSON, nullable=True)
    suggested_playerage = Column(JSON, nullable=True)
    suggested_language_dependence = Column(JSON, nullable=True)

    # Search Column — semantic vectors live in GameEmbedding, not here (see below).
    search_vector = Column(TSVECTOR)

    # Relationships (Using selectin to prevent N+1 query performance issues)
    categories = relationship("Category", secondary="game_categories", lazy="selectin")
    themes = relationship("Theme", secondary="game_themes", lazy="selectin")
    subdomains = relationship("Subdomain", secondary="game_subdomains", lazy="selectin")
    mechanics = relationship("Mechanic", secondary="game_mechanics", lazy="selectin")
    families = relationship("Subfamily", secondary="game_subfamilies", lazy="selectin")
    designers = relationship("Designer", secondary="game_designers", lazy="selectin")
    publishers = relationship("Publisher", secondary="game_publishers", lazy="selectin")
    artists = relationship("Artist", secondary="game_artists", lazy="selectin")

class GameEmbedding(Base):
    """One row per (game, embedding model) — not a 1:1 column on Game, since
    switching or comparing embedding models means having more than one
    model's vectors present at once. `embedding` has no fixed dimension at
    the column level (different models produce different dims); every query
    filters to a single `model` before computing distance, so vectors of
    different dimensions never get compared against each other.
    """
    __tablename__ = "game_embeddings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, ForeignKey("games.bgg_id", ondelete="CASCADE"), nullable=False, index=True)
    model = Column(String, nullable=False, index=True)
    dimension = Column(Integer, nullable=False)
    embedding = Column(Vector(), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    game = relationship("Game")

    __table_args__ = (
        UniqueConstraint("game_id", "model", name="uq_game_embeddings_game_id_model"),
    )

class GameRelation(Base):
    """boardgameexpansion / boardgameimplementation / boardgameintegration
    from jvanelteren. Source data links by name, not BGGId — related_game_id
    is null wherever related_name didn't resolve to an exact match. See
    docs/data/README.md and backend/scripts/build_master_dataset.py.
    """
    __tablename__ = "game_relations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, ForeignKey("games.bgg_id", ondelete="CASCADE"), index=True, nullable=False)
    related_name = Column(String, nullable=False)
    related_game_id = Column(Integer, ForeignKey("games.bgg_id", ondelete="SET NULL"), index=True, nullable=True)
    relation_type = Column(String, nullable=False)  # 'expansion' | 'implementation' | 'integration'

    game = relationship("Game", foreign_keys=[game_id])
    related_game = relationship("Game", foreign_keys=[related_game_id])

class GameRecommendation(Base):
    __tablename__ = "game_recommendations"
    
    game_id = Column(Integer, ForeignKey("games.bgg_id", ondelete="CASCADE"), primary_key=True)
    recommended_game_id = Column(Integer, ForeignKey("games.bgg_id", ondelete="CASCADE"), primary_key=True)
    model = Column(String, primary_key=True)
    
    score = Column(Float, nullable=False)
    reasons = Column(JSON)
    # When this row was (re)computed -- lets a reader tell fresh precomputed
    # data from stale rows left over from a prior run, which the table
    # previously had no way to express at all.
    computed_at = Column(DateTime, nullable=True)

    # Relationships
    game = relationship("Game", foreign_keys=[game_id])
    recommended_game = relationship("Game", foreign_keys=[recommended_game_id], lazy="selectin")

# --- Interactions & Users ---

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    external_user_id = Column(String, unique=True, index=True)

class Rating(Base):
    __tablename__ = "ratings"
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    game_id = Column(Integer, ForeignKey("games.bgg_id", ondelete="CASCADE"), primary_key=True)
    rating = Column(Float, nullable=False)
    timestamp = Column(DateTime, nullable=True)
    game = relationship("Game", backref="ratings")
    user = relationship("User", backref="ratings")

# --- Aspect-Based Sentiment Analysis (ABSA) ---

class ReviewAspect(Base):
    __tablename__ = "review_aspects"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    review_id = Column(Integer, index=True) # Optional link to a reviews table if one exists
    game_id = Column(Integer, ForeignKey("games.bgg_id", ondelete="CASCADE"), index=True)
    aspect = Column(String, nullable=False, index=True)
    sentiment = Column(String, nullable=False) # 'positive', 'negative', 'mixed', 'neutral'
    sentiment_score = Column(Float)
    confidence = Column(Float)
    # Full 3-class softmax, stored explicitly rather than left algebraically
    # recoverable from (sentiment, confidence, sentiment_score) -- the
    # values ARE fully reconstructable from those three (they sum to 1,
    # differ by sentiment_score, and the winner equals confidence), but
    # that requires re-deriving the algebra every time; storing them
    # directly keeps review_aspects a genuinely self-documenting raw record.
    prob_positive = Column(Float)
    prob_neutral = Column(Float)
    prob_negative = Column(Float)
    evidence = Column(Text)
    model_used = Column(String)
    prompt_version = Column(String)
    extracted_at = Column(DateTime, default=func.now())
    
    game = relationship("Game")

class GameAspectAggregate(Base):
    __tablename__ = "game_aspect_aggregates"
    
    game_id = Column(Integer, ForeignKey("games.bgg_id", ondelete="CASCADE"), primary_key=True)
    aspect = Column(String, primary_key=True)
    
    positive_count = Column(Integer, default=0)
    negative_count = Column(Integer, default=0)
    mixed_count = Column(Integer, default=0)
    neutral_count = Column(Integer, default=0)
    total_mentions = Column(Integer, default=0)
    mean_sentiment = Column(Float)
    
    game = relationship("Game")

class Review(Base):
    __tablename__ = "reviews"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    game_id = Column(Integer, ForeignKey("games.bgg_id", ondelete="CASCADE"), index=True)
    rating = Column(Float)
    comment = Column(Text)
    language = Column(String(10), index=True)
    language_confidence = Column(Float, nullable=True)
    # Set by scripts/filter_eligible_reviews.py — app.core.review_quality's
    # weighted score and the final language+hard-filter+dedup+threshold
    # decision, persisted per review rather than recomputed or cached in a
    # JSON file (at ~378K eligible rows out of 4.2M, a real DB column is the
    # right tool). NULL means "not yet scored", not "ineligible".
    quality_score = Column(Float, nullable=True)
    is_absa_eligible = Column(Boolean, nullable=True, index=True)
    # Set by scripts/absa_extract_hf.py on every review it runs inference
    # on, regardless of whether that review produced any storable aspect
    # rows -- true resumability requires tracking "was this attempted", not
    # "did review_aspects end up with a row for it" (a review can be
    # legitimately attempted and yield zero evidence-matched aspects).
    absa_processed_at = Column(DateTime, nullable=True)

    user = relationship("User", backref="reviews", lazy="selectin")
    game = relationship("Game", backref="reviews")

class GameSummary(Base):
    __tablename__ = "game_summaries"
    
    game_id = Column(Integer, ForeignKey("games.bgg_id", ondelete="CASCADE"), primary_key=True)
    summary = Column(Text, nullable=False)
    created_at = Column(DateTime, default=func.now())
    model_used = Column(String)
    
    game = relationship("Game", backref="summary")
