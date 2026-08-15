from sqlalchemy import Column, Integer, String, Float, ForeignKey
from sqlalchemy.orm import relationship
from app.database.session import Base

# --- Join Tables ---

class GameCategory(Base):
    __tablename__ = "game_categories"
    game_id = Column(Integer, ForeignKey("games.bgg_id", ondelete="CASCADE"), primary_key=True)
    category_id = Column(Integer, ForeignKey("categories.id", ondelete="CASCADE"), primary_key=True)

class GameMechanic(Base):
    __tablename__ = "game_mechanics"
    game_id = Column(Integer, ForeignKey("games.bgg_id", ondelete="CASCADE"), primary_key=True)
    mechanic_id = Column(Integer, ForeignKey("mechanics.id", ondelete="CASCADE"), primary_key=True)

class GameDesigner(Base):
    __tablename__ = "game_designers"
    game_id = Column(Integer, ForeignKey("games.bgg_id", ondelete="CASCADE"), primary_key=True)
    designer_id = Column(Integer, ForeignKey("designers.id", ondelete="CASCADE"), primary_key=True)

class GamePublisher(Base):
    __tablename__ = "game_publishers"
    game_id = Column(Integer, ForeignKey("games.bgg_id", ondelete="CASCADE"), primary_key=True)
    publisher_id = Column(Integer, ForeignKey("publishers.id", ondelete="CASCADE"), primary_key=True)

# --- Entity Tables ---

class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, index=True)

class Mechanic(Base):
    __tablename__ = "mechanics"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, index=True)

class Designer(Base):
    __tablename__ = "designers"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, index=True)

class Publisher(Base):
    __tablename__ = "publishers"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, index=True)

# --- Core Table ---

class Game(Base):
    __tablename__ = "games"

    bgg_id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(String)
    year_published = Column(Integer)
    game_weight = Column(Float)
    avg_rating = Column(Float)
    min_players = Column(Integer)
    max_players = Column(Integer)
    mfg_playtime = Column(Integer)
    min_age = Column(Integer)
    image_path = Column(String)
    rank = Column(Integer, nullable=True)

    # Relationships
    categories = relationship("Category", secondary="game_categories")
    mechanics = relationship("Mechanic", secondary="game_mechanics")
    designers = relationship("Designer", secondary="game_designers")
    publishers = relationship("Publisher", secondary="game_publishers")
