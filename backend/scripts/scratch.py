import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.resolve()))

from app.database.session import SessionLocal
from app.database.models import Game

db = SessionLocal()
game = db.query(Game).filter(Game.name.ilike('%Brass: Birmingham%')).first()
if game:
    print(f"BGG ID: {game.bgg_id}")
else:
    print("Not found")
