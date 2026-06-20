#!/usr/bin/env python3
"""
Populate GeForce NOW launch URLs for games in your library.

Two-tier approach:
1. All GFN-available games get a fallback URL to the GFN web app
2. Games with known real UUIDs (from data/gfn_game_ids.json) get direct deep links

To add real game IDs:
1. Go to play.geforcenow.com
2. Find a game and click it
3. Copy the game-id UUID from the browser URL
4. Add to data/gfn_game_ids.json: "Game Title": "uuid-here"
5. Run this script again

Usage:
    python scripts/populate_gfn_game_ids.py
"""

import sys
import os
import json
from difflib import SequenceMatcher
from urllib.parse import quote

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import GfnGame, GameMaster

# GFN URLs
GFN_DEEP_LINK = "https://play.geforcenow.com/games?game-id={game_id}"
GFN_FALLBACK = "https://play.geforcenow.com/mall/#/layout/games"


def similarity(a: str, b: str) -> float:
    """Calculate string similarity (0-1)."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def find_gfn_id(game_title: str, gfn_mapping: dict, threshold: float = 0.7) -> str:
    """Find matching GFN game ID for a title."""
    best_match = None
    best_score = 0

    for gfn_title, gfn_id in gfn_mapping.items():
        if gfn_title.startswith("_"):
            continue

        score = similarity(game_title, gfn_title)
        if score > best_score:
            best_score = score
            best_match = gfn_id

    return best_match if best_score >= threshold else None


def load_gfn_mapping() -> dict:
    """Load GFN game ID mapping from JSON file."""
    mapping_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "data",
        "gfn_game_ids.json"
    )

    if not os.path.exists(mapping_path):
        print(f"[INFO] No gfn_game_ids.json found at {mapping_path}")
        print("[INFO] Will set fallback URLs only. Create the file to add real deep links.")
        return {}

    try:
        with open(mapping_path, 'r') as f:
            mapping = json.load(f)
        # Filter metadata keys
        return {k: v for k, v in mapping.items() if not k.startswith("_")}
    except json.JSONDecodeError as e:
        print(f"[WARN] Invalid JSON in gfn_game_ids.json: {e}")
        return {}


def main():
    """Populate GFN URLs for all games."""
    app = create_app()

    with app.app_context():
        gfn_mapping = load_gfn_mapping()
        real_id_count = len(gfn_mapping)

        print("=" * 80)
        print("GFN URL POPULATION")
        print("=" * 80)
        print(f"Real game IDs in database: {real_id_count}")
        print(f"Fallback URL: {GFN_FALLBACK}")
        print()

        # Get ALL games in gfn_games table
        gfn_games = db.session.query(GfnGame).all()

        if not gfn_games:
            print("No games in gfn_games table!")
            return

        print(f"Total GFN-available games: {len(gfn_games)}\n")

        stats = {"deep_link": 0, "fallback": 0, "skipped": 0}

        for i, gfn_game in enumerate(gfn_games, 1):
            # Get game title
            game = db.session.query(GameMaster).filter(
                GameMaster.game_id == gfn_game.game_id
            ).first()

            if not game:
                stats["skipped"] += 1
                continue

            db_title = game.title

            # Tier 1: Check for real UUID match
            real_id = find_gfn_id(db_title, gfn_mapping) if gfn_mapping else None

            if real_id:
                # Real deep link - set URL directly (don't set gfn_game_id 
                # because the view constructs a wrong URL format from it)
                gfn_game.gfn_url = GFN_DEEP_LINK.format(game_id=real_id)
                stats["deep_link"] += 1
                print(f"  🎯 [{i}/{len(gfn_games)}] {db_title} → DEEP LINK ({real_id[:16]}...)")
            else:
                # Tier 2: Fallback to GFN web app
                gfn_game.gfn_url = GFN_FALLBACK
                stats["fallback"] += 1
                if i <= 20:  # Only show first 20
                    print(f"  ☁️  [{i}/{len(gfn_games)}] {db_title} → GFN Web App")

            db.session.add(gfn_game)

        if len(gfn_games) > 20 and stats["fallback"] > 20:
            print(f"  ... and {stats['fallback'] - 20} more with fallback URLs")

        # Commit
        db.session.commit()

        # Summary
        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)
        print(f"🎯 Direct deep links:  {stats['deep_link']}")
        print(f"☁️  Fallback (GFN app): {stats['fallback']}")
        print(f"⏭️  Skipped:            {stats['skipped']}")
        print(f"📊 Total processed:     {stats['deep_link'] + stats['fallback'] + stats['skipped']}")
        print("=" * 80)

        if stats["deep_link"] + stats["fallback"] > 0:
            print(f"\n✅ {stats['deep_link'] + stats['fallback']} games now have GFN launch URLs!")
            print("Refresh your browser to see the updates.\n")

        print("📖 To add REAL deep links for specific games:")
        print("   1. Go to play.geforcenow.com")
        print("   2. Find a game and click it")
        print("   3. Copy the game-id UUID from the URL bar")
        print("   4. Add to data/gfn_game_ids.json:")
        print('      "Game Title": "uuid-from-url-bar"')
        print("   5. Run this script again\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
