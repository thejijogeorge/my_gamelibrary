#!/usr/bin/env python3
"""
Debug script to find why games aren't matching.
Shows all games without GFN IDs and their exact titles in database.
"""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import GfnGame, GameMaster


def main():
    """Debug game matching issues."""
    app = create_app()
    app_context = app.app_context()
    app_context.push()
    
    # Load GFN mapping
    mapping_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "data",
        "gfn_game_ids.json"
    )
    
    with open(mapping_path, 'r') as f:
        gfn_mapping = json.load(f)
    
    # Filter out metadata
    gfn_titles = {k: v for k, v in gfn_mapping.items() if not k.startswith("_")}
    
    print("=" * 100)
    print("GAME MATCHING DEBUG")
    print("=" * 100 + "\n")
    
    # Get all games without GFN IDs
    games_without_gfn = db.session.query(GfnGame).filter(
        GfnGame.gfn_game_id == None
    ).all()
    
    print(f"🎮 Total games without GFN IDs: {len(games_without_gfn)}\n")
    
    # Get game titles from database
    print("Sample of games in your database (without GFN IDs):")
    print("-" * 100)
    
    for gfn_game in games_without_gfn[:50]:  # Show first 50
        game = db.session.query(GameMaster).filter(
            GameMaster.game_id == gfn_game.game_id
        ).first()
        
        if game:
            db_title = game.title
            
            # Check if there's a close match in GFN database
            closest_match = None
            closest_score = 0
            
            from difflib import SequenceMatcher
            
            for gfn_title in gfn_titles.keys():
                score = SequenceMatcher(None, db_title.lower(), gfn_title.lower()).ratio()
                if score > closest_score:
                    closest_score = score
                    closest_match = gfn_title
            
            status = "✅ MATCH" if closest_score >= 0.7 else "❌ NO MATCH"
            print(f"{status} | DB: '{db_title}' | Match: '{closest_match}' ({closest_score:.2%})")
    
    print("\n" + "=" * 100)
    print("GAMES IN GFN DATABASE (for reference):")
    print("=" * 100 + "\n")
    
    for gfn_title in sorted(gfn_titles.keys()):
        print(f"  • {gfn_title}")
    
    print("\n" + "=" * 100)
    print("SOLUTION:")
    print("=" * 100)
    print("""
If you see mismatches like:
  DB: "Baldurs Gate 3" vs GFN: "Baldur's Gate 3"
  
Options:
1. Update data/gfn_game_ids.json to match your database titles exactly
   - OR -
2. Update the game titles in your database to match GFN titles
   - OR -
3. Add BOTH variations to gfn_game_ids.json

Example:
  "Baldurs Gate 3": "7f1c2a3d-4e5f-6789-abcd-ef1234567890",
  "Baldur's Gate 3": "7f1c2a3d-4e5f-6789-abcd-ef1234567890",

Then run: python scripts/populate_gfn_game_ids.py
    """)


if __name__ == "__main__":
    main()
