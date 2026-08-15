from sqlalchemy import Column, Integer, String, Float, Boolean, Text
from app.database.session import Base

class Game(Base):
    __tablename__ = "games"

    bgg_id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(Text)
    year_published = Column(Integer)
    game_weight = Column(Float)
    avg_rating = Column(Float)
    min_players = Column(Integer)
    max_players = Column(Integer)
    mfg_playtime = Column(Integer)
    min_age = Column(Integer)
    image_path = Column(String)
    rank = Column(Integer, nullable=True)
    categories = Column(String, nullable=True)
