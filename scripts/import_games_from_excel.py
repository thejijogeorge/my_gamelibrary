#!/usr/bin/env python3
"""
Import game library from Excel file into Postgres with IGDB matching.

Usage:
    python scripts/import_games_from_excel.py <path_to_excel_file>

Example:
    python scripts/import_games_from_excel.py ~/Downloads/Epic_Games_Library_Final.xlsx
"""

import sys
import os
import json
from pathlib import Path
from typing import Optional, Tuple
from difflib import SequenceMatcher

import openpyxl
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import Platform, Account, GameMaster, OwnedGameSteam, OwnedGameEpic, OwnedGameGog, GfnGame


class GameImporter:
    """Import games from Excel to Postgres."""

    def __init__(self, excel_path: str, igdb_enabled: bool = False):
        """
        Initialize importer.
        
        Args:
            excel_path: Path to the Excel file
            igdb_enabled: If True, try to match with IGDB API (requires API keys in .env)
        """
        self.excel_path = Path(excel_path)
        self.igdb_enabled = igdb_enabled
        self.wb = openpyxl.load_workbook(excel_path)
        
        # App and DB
        self.app = create_app()
        self.app_context = self.app.app_context()
        self.app_context.push()
        
        # Stats
        self.stats = {
            "games_master_created": 0,
            "platforms_created": 0,
            "accounts_created": 0,
            "owned_games_steam": 0,
            "owned_games_epic": 0,
            "owned_games_gog": 0,
            "gfn_games_linked": 0,
            "warnings": [],
        }

    def log(self, msg: str, level: str = "INFO"):
        """Log a message."""
        print(f"[{level}] {msg}")

    def warn(self, msg: str):
        """Log warning."""
        self.log(msg, "WARN")
        self.stats["warnings"].append(msg)

    def similarity(self, a: str, b: str) -> float:
        """Calculate string similarity (0-1)."""
        return SequenceMatcher(None, a.lower(), b.lower()).ratio()

    def normalize_title(self, title: str) -> str:
        """Normalize game title for matching."""
        return title.lower().strip()

    def get_or_create_game_master(self, title: str) -> GameMaster:
        """
        Get or create a game in games_master.
        
        For now, creates placeholder with IGDB matching to be added later.
        """
        normalized = self.normalize_title(title)
        
        # Check if already exists
        existing = db.session.query(GameMaster).filter(
            db.func.lower(GameMaster.title) == normalized
        ).first()
        
        if existing:
            return existing
        
        # Create new
        game = GameMaster(
            title=title,
            igdb_id=None,  # Would be filled in by separate IGDB matching job
            cover_url=None,
            genres=None,
        )
        db.session.add(game)
        db.session.flush()  # Get the game_id
        self.stats["games_master_created"] += 1
        self.log(f"Created game_master: {title}", "DEBUG")
        
        return game

    def setup_platforms_and_accounts(self):
        """Create platforms and accounts from Profile sheet."""
        profile_ws = self.wb["Profile"]
        
        # Map: platform_name -> list of (account_type, account_id)
        accounts_to_create = {
            "Steam": [("jijo_george_max", "jijo_george_max")],
            "Epic": [
                ("Geekstradamus01", "Geekstradamus01"),
                ("Geekstradamus", "Geekstradamus"),
            ],
            "GOG": [("jijo_george", "jijo_george")],
        }
        
        for platform_name, account_list in accounts_to_create.items():
            # Get or create platform
            platform = db.session.query(Platform).filter_by(name=platform_name).first()
            if not platform:
                platform = Platform(name=platform_name)
                db.session.add(platform)
                db.session.flush()
                self.stats["platforms_created"] += 1
                self.log(f"Created platform: {platform_name}")
            
            # Create accounts
            for display_name, username in account_list:
                account = db.session.query(Account).filter_by(
                    platform_id=platform.platform_id, username=username
                ).first()
                if not account:
                    account = Account(
                        platform_id=platform.platform_id,
                        username=username,
                        display_name=display_name,
                    )
                    db.session.add(account)
                    db.session.flush()
                    self.stats["accounts_created"] += 1
                    self.log(f"Created account: {platform_name}/{username}")

    def import_epic_games(self):
        """Import Epic Games from the two Epic library sheets."""
        for sheet_name in ["Epic Library (Geekstradamus01)", "Epic Library (Geekstradamus)"]:
            if sheet_name not in self.wb.sheetnames:
                continue
            
            ws = self.wb[sheet_name]
            # Extract account name from sheet name
            account_name = sheet_name.split("(")[1].rstrip(")")
            
            # Get account
            account = db.session.query(Account).join(Platform).filter(
                Platform.name == "Epic", Account.username == account_name
            ).first()
            
            if not account:
                self.warn(f"Account not found: Epic/{account_name}")
                continue
            
            # Import games
            for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
                try:
                    # Columns: No., Title, Platform, Time Played, Notes
                    title = row[1]
                    if not title:
                        continue
                    
                    # Get or create game
                    game = self.get_or_create_game_master(title)
                    
                    # Check if already owned
                    existing = db.session.query(OwnedGameEpic).filter_by(
                        account_id=account.account_id, epic_item_id=title  # Use title as temp ID
                    ).first()
                    if existing:
                        continue
                    
                    # Create owned game entry
                    owned = OwnedGameEpic(
                        account_id=account.account_id,
                        game_id=game.game_id,
                        epic_item_id=title,  # TODO: fetch actual epic_item_id from API
                        epic_namespace=None,  # TODO: fetch from API
                    )
                    db.session.add(owned)
                    self.stats["owned_games_epic"] += 1
                    
                except Exception as e:
                    self.warn(f"Error importing Epic game at row {row_idx}: {e}")
        
        db.session.commit()
        self.log(f"Imported {self.stats['owned_games_epic']} Epic games")

    def import_steam_games(self):
        """Import Steam games from the Steam sheet."""
        if "Steam Games (jijo_george_max)" not in self.wb.sheetnames:
            return
        
        ws = self.wb["Steam Games (jijo_george_max)"]
        
        # Get account
        account = db.session.query(Account).join(Platform).filter(
            Platform.name == "Steam", Account.username == "jijo_george_max"
        ).first()
        
        if not account:
            self.warn("Account not found: Steam/jijo_george_max")
            return
        
        # Import games
        for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            try:
                # Columns: No., Title, Platform, Price/Hour, Price, Hours Played, Review Score
                title = row[1]
                if not title:
                    continue
                
                # Get or create game
                game = self.get_or_create_game_master(title)
                
                # Check if already owned (use title as temp steam_appid)
                existing = db.session.query(OwnedGameSteam).filter_by(
                    account_id=account.account_id, steam_appid=hash(title) % (10**9)
                ).first()
                if existing:
                    continue
                
                # Create owned game entry
                owned = OwnedGameSteam(
                    account_id=account.account_id,
                    game_id=game.game_id,
                    steam_appid=hash(title) % (10**9),  # TODO: fetch actual appid from Steam API
                    playtime_minutes=0,
                    last_played=None,
                )
                db.session.add(owned)
                self.stats["owned_games_steam"] += 1
                
            except Exception as e:
                self.warn(f"Error importing Steam game at row {row_idx}: {e}")
        
        db.session.commit()
        self.log(f"Imported {self.stats['owned_games_steam']} Steam games")

    def import_gog_games(self):
        """Import GOG games from the GOG sheet."""
        if "GOG Games (jijo_george)" not in self.wb.sheetnames:
            return
        
        ws = self.wb["GOG Games (jijo_george)"]
        
        # Get account
        account = db.session.query(Account).join(Platform).filter(
            Platform.name == "GOG", Account.username == "jijo_george"
        ).first()
        
        if not account:
            self.warn("Account not found: GOG/jijo_george")
            return
        
        # Import games
        for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            try:
                # Columns: No., Title, Platform
                title = row[1]
                if not title:
                    continue
                
                # Get or create game
                game = self.get_or_create_game_master(title)
                
                # Check if already owned
                existing = db.session.query(OwnedGameGog).filter_by(
                    account_id=account.account_id, gog_product_id=title
                ).first()
                if existing:
                    continue
                
                # Create owned game entry
                owned = OwnedGameGog(
                    account_id=account.account_id,
                    game_id=game.game_id,
                    gog_product_id=title,  # TODO: fetch actual product_id from GOG API
                )
                db.session.add(owned)
                self.stats["owned_games_gog"] += 1
                
            except Exception as e:
                self.warn(f"Error importing GOG game at row {row_idx}: {e}")
        
        db.session.commit()
        self.log(f"Imported {self.stats['owned_games_gog']} GOG games")

    def import_gfn_catalog(self):
        """Import GeForce NOW catalog and match to games_master."""
        if "GeForce NOW Catalog" not in self.wb.sheetnames:
            return
        
        ws = self.wb["GeForce NOW Catalog"]
        
        gfn_games_created = 0
        
        for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            try:
                # Columns: No., Title, Publisher, Available Store(s)
                title = row[1]
                available_stores = row[3] or ""
                
                if not title:
                    continue
                
                # Get or create game
                game = self.get_or_create_game_master(title)
                
                # Check if GFN entry already exists
                existing = db.session.query(GfnGame).filter_by(game_id=game.game_id).first()
                if existing:
                    continue
                
                # Parse available stores
                stores_lower = available_stores.lower()
                available_on_steam = "steam" in stores_lower
                available_on_epic = "epic" in stores_lower
                available_on_gog = "gog" in stores_lower
                
                # Create GFN entry
                gfn = GfnGame(
                    game_id=game.game_id,
                    available_on_steam=available_on_steam,
                    available_on_epic=available_on_epic,
                    available_on_gog=available_on_gog,
                    gfn_deeplink_url=f"https://play.geforcenow.com/launch/{title.lower().replace(' ', '-')}",
                )
                db.session.add(gfn)
                gfn_games_created += 1
                self.stats["gfn_games_linked"] += gfn_games_created
                
            except Exception as e:
                self.warn(f"Error importing GFN game at row {row_idx}: {e}")
        
        db.session.commit()
        self.log(f"Imported {gfn_games_created} GeForce NOW games")

    def run(self):
        """Run the full import process."""
        try:
            self.log("Starting game library import...")
            
            # Step 1: Setup platforms and accounts
            self.log("Step 1: Setting up platforms and accounts")
            self.setup_platforms_and_accounts()
            
            # Step 2: Import games from each platform
            self.log("Step 2: Importing games from all platforms")
            self.import_epic_games()
            self.import_steam_games()
            self.import_gog_games()
            self.import_gfn_catalog()
            
            # Commit all
            db.session.commit()
            
            # Print summary
            self.print_summary()
            
        except Exception as e:
            db.session.rollback()
            self.log(f"ERROR: {e}", "ERROR")
            raise
        finally:
            self.app_context.pop()

    def print_summary(self):
        """Print import summary."""
        print("\n" + "="*80)
        print("IMPORT SUMMARY")
        print("="*80)
        print(f"✅ Games created in games_master: {self.stats['games_master_created']}")
        print(f"✅ Platforms created: {self.stats['platforms_created']}")
        print(f"✅ Accounts created: {self.stats['accounts_created']}")
        print(f"✅ Steam games imported: {self.stats['owned_games_steam']}")
        print(f"✅ Epic games imported: {self.stats['owned_games_epic']}")
        print(f"✅ GOG games imported: {self.stats['owned_games_gog']}")
        print(f"✅ GeForce NOW games linked: {self.stats['gfn_games_linked']}")
        
        if self.stats["warnings"]:
            print(f"\n⚠️  Warnings ({len(self.stats['warnings'])}):")
            for warning in self.stats["warnings"][:10]:  # Show first 10
                print(f"  - {warning}")
            if len(self.stats["warnings"]) > 10:
                print(f"  ... and {len(self.stats['warnings']) - 10} more")
        
        print("="*80 + "\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/import_games_from_excel.py <path_to_excel_file>")
        sys.exit(1)
    
    excel_file = sys.argv[1]
    if not os.path.exists(excel_file):
        print(f"Error: File not found: {excel_file}")
        sys.exit(1)
    
    importer = GameImporter(excel_file, igdb_enabled=False)
    importer.run()
