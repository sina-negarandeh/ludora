from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, JSON, Text
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

# --- Entity Tables ---

class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, index=True, nullable=False)

class Theme(Base):
    __tablename__ = "themes"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, index=True, nullable=False)

class Mechanic(Base):
    __tablename__ = "mechanics"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, index=True, nullable=False)

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
    category_ranks = Column(JSON, nullable=True)

    # Search and Vector Columns
    embedding = Column(Vector(384))
    embedding_model = Column(String)
    embedding_updated_at = Column(DateTime)
    search_vector = Column(TSVECTOR)

    # Relationships
    categories = relationship("Category", secondary="game_categories")
    themes = relationship("Theme", secondary="game_themes")
    mechanics = relationship("Mechanic", secondary="game_mechanics")
    designers = relationship("Designer", secondary="game_designers")
    publishers = relationship("Publisher", secondary="game_publishers")
    artists = relationship("Artist", secondary="game_artists")

class GameRecommendation(Base):
    __tablename__ = "game_recommendations"
    
    game_id = Column(Integer, ForeignKey("games.bgg_id", ondelete="CASCADE"), primary_key=True)
    recommended_game_id = Column(Integer, ForeignKey("games.bgg_id", ondelete="CASCADE"), primary_key=True)
    model = Column(String, primary_key=True)
    
    score = Column(Float, nullable=False)
    reasons = Column(JSON)
    
    # Relationships
    game = relationship("Game", foreign_keys=[game_id])
    recommended_game = relationship("Game", foreign_keys=[recommended_game_id])

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
    
    user = relationship("User", backref="ratings")
    game = relationship("Game", backref="ratings")

class Review(Base):
    __tablename__ = "reviews"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    game_id = Column(Integer, ForeignKey("games.bgg_id", ondelete="CASCADE"), index=True)
    rating = Column(Float)
    comment = Column(Text)
    created_at = Column(DateTime, nullable=True)
    
    user = relationship("User", backref="reviews")
    game = relationship("Game", backref="reviews")
