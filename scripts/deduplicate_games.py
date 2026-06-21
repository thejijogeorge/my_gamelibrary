#!/usr/bin/env python3
"""
Remove duplicate games from owned_games tables.

For each account/platform combination, keeps only one entry per game_id.
Duplicates can occur from multiple imports or data entry errors.

Usage:
    python scripts/deduplicate_games.py          # Interactive (asks for confirmation)
    python scripts/deduplicate_games.py --yes    # Auto-confirm (for Docker/scripts)

This will:
1. Show what duplicates exist
2. Ask for confirmation
3. Delete duplicates, keeping the oldest entry (lowest ID)
"""

import sys
import os
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import OwnedGameSteam, OwnedGameEpic, OwnedGameGog


def deduplicate_table(model_class, account_id_col, game_id_col, table_name):
    """
    Remove duplicates from an owned_games table.
    
    Keeps the entry with the lowest ID (oldest), deletes the rest.
    
    Args:
        model_class: SQLAlchemy model (OwnedGamesSteam, OwnedGamesEpic, OwnedGamesGOG)
        account_id_col: Column name for account ID
        game_id_col: Column name for game ID
        table_name: Human-readable table name
    """
    print(f"\n{'='*80}")
    print(f"Deduplicating {table_name}")
    print(f"{'='*80}")
    
    # Find duplicates: group by (account_id, game_id), count > 1
    duplicates_query = db.session.execute(
        db.text(f"""
            SELECT {account_id_col}, {game_id_col}, COUNT(*) as count
            FROM {table_name}
            GROUP BY {account_id_col}, {game_id_col}
            HAVING COUNT(*) > 1
            ORDER BY count DESC
        """)
    ).fetchall()
    
    if not duplicates_query:
        print(f"✅ No duplicates found in {table_name}")
        return 0
    
    total_duplicates = len(duplicates_query)
    total_to_delete = 0
    
    print(f"⚠️  Found {total_duplicates} account/game combinations with duplicates:\n")
    
    for account_id, game_id, count in duplicates_query:
        print(f"  Account {account_id}, Game {game_id}: {count} entries (will keep 1, delete {count-1})")
        total_to_delete += (count - 1)
    
    print(f"\n📊 Total entries to delete: {total_to_delete}")
    
    # Check for --yes flag (auto-confirm for Docker/non-interactive use)
    auto_confirm = "--yes" in sys.argv or "-y" in sys.argv
    
    if auto_confirm:
        print("\n🔧 Auto-confirmed via --yes flag.")
    else:
        response = input(f"\n❓ Delete {total_to_delete} duplicate entries? (yes/no): ").strip().lower()
        if response != "yes":
            print("❌ Cancelled. No changes made.")
            return 0
    
    # Delete duplicates (keep lowest ID = oldest entry)
    deleted_count = 0
    
    for account_id, game_id, count in duplicates_query:
        # Get all IDs for this duplicate group
        ids_query = db.session.execute(
            db.text(f"""
                SELECT id FROM {table_name}
                WHERE {account_id_col} = {account_id} AND {game_id_col} = {game_id}
                ORDER BY id ASC
            """)
        ).fetchall()
        
        ids_to_delete = [row[0] for row in ids_query[1:]]  # Keep first, delete rest
        
        if ids_to_delete:
            # Delete duplicates
            db.session.execute(
                db.text(f"DELETE FROM {table_name} WHERE id IN ({','.join(map(str, ids_to_delete))})")
            )
            deleted_count += len(ids_to_delete)
    
    db.session.commit()
    print(f"\n✅ Deleted {deleted_count} duplicate entries from {table_name}")
    
    return deleted_count


def main():
    """Remove duplicates from all owned_games tables."""
    app = create_app()
    
    with app.app_context():
        print("\n" + "="*80)
        print("GAME LIBRARY DEDUPLICATION TOOL")
        print("="*80)
        print("\nThis will remove duplicate game entries for the same account/platform.")
        print("Only the oldest entry (by ID) will be kept.\n")
        
        total_deleted = 0
        
        # Deduplicate each table
        total_deleted += deduplicate_table(
            OwnedGameSteam,
            "account_id",
            "game_id",
            "owned_games_steam"
        )
        
        total_deleted += deduplicate_table(
            OwnedGameEpic,
            "account_id",
            "game_id",
            "owned_games_epic"
        )
        
        total_deleted += deduplicate_table(
            OwnedGameGog,
            "account_id",
            "game_id",
            "owned_games_gog"
        )
        
        # Show final stats
        print(f"\n{'='*80}")
        print("DEDUPLICATION COMPLETE")
        print(f"{'='*80}")
        
        # Get updated counts
        steam_count = db.session.query(OwnedGameSteam).count()
        epic_count = db.session.query(OwnedGameEpic).count()
        gog_count = db.session.query(OwnedGameGog).count()
        total_count = steam_count + epic_count + gog_count
        
        print(f"\n📊 Current game counts:")
        print(f"  Steam: {steam_count} games")
        print(f"  Epic: {epic_count} games")
        print(f"  GOG: {gog_count} games")
        print(f"  Total: {total_count} games")
        print(f"\n✅ Total deleted: {total_deleted} duplicates")
        
        if total_deleted > 0:
            print(f"\n🔄 Refresh your browser to see the updated list (no restart needed)!")
            print(f"   http://localhost:5000")
        else:
            print(f"\nℹ️  No duplicates were found or deleted.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
