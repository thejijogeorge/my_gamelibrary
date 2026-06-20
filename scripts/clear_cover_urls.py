#!/usr/bin/env python3
"""
Clear all cover URLs from games_master to force re-fetch with high quality.

This removes all cover_url values so they can be re-fetched with the new
t_1080p format (instead of old blurry t_cover_big format).

Usage:
    python scripts/clear_cover_urls.py
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import GameMaster


def main():
    """Clear all cover URLs from database."""
    app = create_app()
    
    with app.app_context():
        print("\n" + "="*80)
        print("COVER URL CLEARING TOOL")
        print("="*80)
        print("\nThis will clear all cover URLs so they can be re-fetched with")
        print("high quality (t_1080p format instead of blurry t_cover_big).\n")
        
        # Count games with covers and IGDB IDs
        games_with_covers = db.session.query(GameMaster).filter(
            GameMaster.cover_url != None
        ).count()
        
        games_with_igdb_ids = db.session.query(GameMaster).filter(
            GameMaster.igdb_id != None
        ).count()
        
        print(f"⚠️  Found {games_with_covers} games with cover URLs")
        print(f"⚠️  Found {games_with_igdb_ids} games with IGDB IDs")
        print(f"Both will be cleared and re-fetched.\n")
        
        # Ask for confirmation
        response = input("❓ Clear all cover URLs and IGDB IDs? (yes/no): ").strip().lower()
        
        if response != "yes":
            print("❌ Cancelled. No changes made.")
            return
        
        # Clear all cover URLs AND IGDB IDs
        db.session.query(GameMaster).update(
            {
                GameMaster.cover_url: None,
                GameMaster.igdb_id: None
            },
            synchronize_session=False
        )
        db.session.commit()
        
        print(f"\n✅ Cleared {games_with_covers} cover URLs")
        print(f"✅ Cleared {games_with_igdb_ids} IGDB IDs")
        print(f"\n🔄 Next steps:")
        print(f"   1. Run: docker exec gamelibrary-web python scripts/fetch_igdb_metadata.py")
        print(f"   2. Refresh: http://localhost:5000")
        print(f"\nYour covers will now be fetched with high quality (t_1080p)! 🎨")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
