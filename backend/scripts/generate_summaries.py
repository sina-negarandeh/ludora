import sys
import os

# Add backend directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database.session import SessionLocal
from app.services.summarization_service import SummarizationService
from app.database.models import Game

def main():
    game_name = "Brass: Birmingham"
    
    with SessionLocal() as db:
        game = db.query(Game).filter(Game.name == game_name).first()
        if not game:
            print(f"Game '{game_name}' not found.")
            return

        print(f"Found game: {game.name} (BGG ID: {game.bgg_id})")
        print("Initializing Summarization Service...")
        
        summarizer = SummarizationService(db)
        
        summary_obj = summarizer.generate_game_summary(game.bgg_id)
        
        if summary_obj:
            print("\n" + "="*50)
            print("FINAL CUSTOMERS SAY SUMMARY:")
            print("="*50)
            print(summary_obj.summary)
        else:
            print(f"Failed to generate summary for {game.name}.")

if __name__ == "__main__":
    main()
