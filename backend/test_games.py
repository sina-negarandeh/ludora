from app.database.session import SessionLocal
from app.services.game_service import GameService

def test():
    db = SessionLocal()
    try:
        service = GameService(db)
        total, games = service.get_games(limit=2)
        print(f"Total: {total}, Games returned: {len(games)}")
    except Exception as e:
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    test()
