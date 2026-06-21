#!/usr/bin/env python3
"""
Fetch game metadata from IGDB API and update games_master with cover art,
genres, release dates, and IGDB IDs.

Usage:
    python scripts/fetch_igdb_metadata.py

Requires environment variables:
    IGDB_CLIENT_ID: Your Twitch Client ID
    IGDB_ACCESS_TOKEN: Your Twitch Client Secret (will be exchanged for OAuth token)
"""

import sys
import os
import json
import time
from typing import Optional
import requests
from difflib import SequenceMatcher

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import GameMaster


class IGDBClient:
    """IGDB API client for fetching game metadata."""
    
    BASE_URL = "https://api.igdb.com/v4"
    OAUTH_URL = "https://id.twitch.tv/oauth2/token"
    
    def __init__(self, client_id: str, client_secret: str):
        """Initialize IGDB client and get OAuth token."""
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = None
        self.headers = {}
        
        # Get OAuth token
        self._get_oauth_token()
        self.rate_limit_remaining = 4
        self.rate_limit_reset = 0
    
    def _get_oauth_token(self):
        """Exchange Client ID/Secret for OAuth access token."""
        print("[INFO] Requesting OAuth token from Twitch...")
        print(f"[DEBUG] Client ID: {self.client_id[:10]}..." if self.client_id else "[DEBUG] Client ID: NOT SET")
        print(f"[DEBUG] Client Secret: {self.client_secret[:10]}..." if self.client_secret else "[DEBUG] Client Secret: NOT SET")
        
        try:
            response = requests.post(
                self.OAUTH_URL,
                params={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "grant_type": "client_credentials",
                },
                timeout=10,
            )
            
            print(f"[DEBUG] OAuth response status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                self.access_token = data.get("access_token")
                
                if self.access_token:
                    self.headers = {
                        "Client-ID": self.client_id,
                        "Authorization": f"Bearer {self.access_token}",
                    }
                    print("[INFO] ✅ Successfully obtained OAuth token")
                else:
                    raise ValueError("No access token in response")
            else:
                print(f"[ERROR] OAuth response body: {response.text}")
                raise ValueError(f"OAuth request failed: {response.status_code} - {response.text}")
        
        except Exception as e:
            print(f"[ERROR] Failed to get OAuth token: {e}")
            raise
    
    def _handle_rate_limit(self):
        """Handle IGDB rate limiting (4 requests per second)."""
        if self.rate_limit_remaining <= 0:
            sleep_time = max(0.1, self.rate_limit_reset - time.time())
            print(f"[RATE LIMIT] Sleeping {sleep_time:.1f}s...")
            time.sleep(sleep_time)
        else:
            time.sleep(0.25)  # 4 requests per second = 250ms between requests
    
    def search_games(self, query: str, limit: int = 5) -> list:
        """
        Search for games by title.
        
        Args:
            query: Game title to search for
            limit: Max results to return
        
        Returns:
            List of matching games from IGDB
        """
        self._handle_rate_limit()
        
        # Build IGDB query
        igdb_query = f"""
            search "{query}";
            fields id, name, cover.url, genres.name, first_release_date,
                   summary, rating, total_rating, total_rating_count,
                   themes.name, game_modes.name,
                   involved_companies.company.name, involved_companies.developer, involved_companies.publisher;
            limit {limit};
        """
        
        try:
            response = requests.post(
                f"{self.BASE_URL}/games",
                headers=self.headers,
                data=igdb_query,
                timeout=10,
            )
            
            # Track rate limits
            if "X-Rate-Limit-Remaining" in response.headers:
                self.rate_limit_remaining = int(response.headers["X-Rate-Limit-Remaining"])
            if "X-Rate-Limit-Reset" in response.headers:
                self.rate_limit_reset = int(response.headers["X-Rate-Limit-Reset"])
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"[ERROR] IGDB API error: {response.status_code} - {response.text[:200]}")
                return []
        
        except Exception as e:
            print(f"[ERROR] Request failed: {e}")
            return []
    
    def get_cover_url(self, cover_id: str) -> Optional[str]:
        """Convert IGDB cover ID to full image URL."""
        if not cover_id:
            return None
        # IGDB cover URLs format: //images.igdb.com/igdb/image/upload/t_cover_big/{cover_id}.jpg
        return f"https://images.igdb.com/igdb/image/upload/t_cover_big/{cover_id}.jpg"
    
    def get_game_by_igdb_id(self, igdb_id: int) -> Optional[dict]:
        """
        Fetch a game by its IGDB ID (for updating details of already-matched games).
        
        Args:
            igdb_id: IGDB game ID
        
        Returns:
            Game data dict or None
        """
        self._handle_rate_limit()
        
        igdb_query = f"""
            fields id, name, cover.url, genres.name, first_release_date,
                   summary, rating, total_rating, total_rating_count,
                   themes.name, game_modes.name,
                   involved_companies.company.name, involved_companies.developer, involved_companies.publisher;
            where id = {igdb_id};
            limit 1;
        """
        
        try:
            response = requests.post(
                f"{self.BASE_URL}/games",
                headers=self.headers,
                data=igdb_query,
                timeout=10,
            )
            
            if "X-Rate-Limit-Remaining" in response.headers:
                self.rate_limit_remaining = int(response.headers["X-Rate-Limit-Remaining"])
            
            if response.status_code == 200:
                results = response.json()
                return results[0] if results else None
            else:
                print(f"[ERROR] IGDB API error: {response.status_code} - {response.text[:200]}")
                return None
        
        except Exception as e:
            print(f"[ERROR] Request failed: {e}")
            return None


class GameMatcher:
    """Match local game titles to IGDB entries."""
    
    @staticmethod
    def similarity(a: str, b: str) -> float:
        """Calculate string similarity (0-1)."""
        return SequenceMatcher(None, a.lower(), b.lower()).ratio()
    
    @staticmethod
    def find_best_match(local_title: str, igdb_results: list, threshold: float = 0.7):
        """
        Find best matching IGDB game.
        
        Args:
            local_title: Your local game title
            igdb_results: List of IGDB results
            threshold: Minimum similarity score (0-1)
        
        Returns:
            Best matching IGDB game or None
        """
        if not igdb_results:
            return None
        
        best_match = None
        best_score = 0
        
        for igdb_game in igdb_results:
            score = GameMatcher.similarity(local_title, igdb_game.get("name", ""))
            if score > best_score:
                best_score = score
                best_match = igdb_game
        
        # Only return if above threshold
        return best_match if best_score >= threshold else None


class IGDBMetadataFetcher:
    """Fetch and update game metadata from IGDB."""
    
    def __init__(self):
        """Initialize fetcher."""
        self.app = create_app()
        self.app_context = self.app.app_context()
        self.app_context.push()
        
        # Initialize IGDB client
        client_id = os.environ.get("IGDB_CLIENT_ID")
        client_secret = os.environ.get("IGDB_ACCESS_TOKEN")  # This is actually the Client Secret
        
        if not client_id or not client_secret:
            raise ValueError("IGDB_CLIENT_ID and IGDB_ACCESS_TOKEN must be set in .env")
        
        self.igdb = IGDBClient(client_id, client_secret)
        self.matcher = GameMatcher()
        
        # Stats
        self.stats = {
            "total_games": 0,
            "updated": 0,
            "skipped": 0,
            "failed": 0,
        }
    
    def log(self, msg: str, level: str = "INFO"):
        """Log a message."""
        print(f"[{level}] {msg}")
    
    def fetch_and_update(self, batch_size: int = 100):
        """
        Fetch metadata for games user actually owns (Steam, Epic, GOG).
        
        Args:
            batch_size: Process this many games before committing
        """
        # Only get games that are in owned_games tables (Steam, Epic, GOG)
        # NOT the entire GFN catalog
        games = db.session.execute(
            db.text("""
                SELECT DISTINCT g.game_id, g.title, g.igdb_id
                FROM games_master g
                WHERE (
                    EXISTS (SELECT 1 FROM owned_games_steam WHERE game_id = g.game_id)
                    OR EXISTS (SELECT 1 FROM owned_games_epic WHERE game_id = g.game_id)
                    OR EXISTS (SELECT 1 FROM owned_games_gog WHERE game_id = g.game_id)
                )
                AND g.igdb_id IS NULL
                ORDER BY g.title
            """)
        ).fetchall()
        
        self.stats["total_games"] = len(games)
        self.log(f"Found {len(games)} owned games without IGDB metadata (excluding GFN catalog)")
        
        if not games:
            self.log("All owned games already have IGDB metadata!")
            return
        
        # Process in batches
        for i, (game_id, title, igdb_id) in enumerate(games, 1):
            try:
                self.log(f"[{i}/{len(games)}] Processing: {title}")
                
                # Get the actual game object
                game = db.session.get(GameMaster, game_id)
                if not game:
                    continue
                
                # Search IGDB
                results = self.igdb.search_games(title, limit=5)
                
                if not results:
                    self.log(f"  No results found", "WARN")
                    self.stats["failed"] += 1
                    continue
                
                # Find best match
                best_match = self.matcher.find_best_match(title, results)
                
                if not best_match:
                    self.log(f"  No good match (threshold not met)", "WARN")
                    self.stats["failed"] += 1
                    continue
                
                # Extract metadata
                new_igdb_id = best_match.get("id")
                igdb_name = best_match.get("name", "")
                cover_data = best_match.get("cover")
                genres = best_match.get("genres", [])
                first_release_date = best_match.get("first_release_date")
                summary = best_match.get("summary")
                rating = best_match.get("rating")
                total_rating = best_match.get("total_rating")
                total_rating_count = best_match.get("total_rating_count")
                themes = best_match.get("themes", [])
                game_modes = best_match.get("game_modes", [])
                involved_companies = best_match.get("involved_companies", [])
                
                # Build cover URL correctly
                cover_url = None
                if cover_data:
                    cover_id = cover_data.get("url") if isinstance(cover_data, dict) else cover_data
                    
                    if cover_id:
                        # IGDB returns paths like: //images.igdb.com/igdb/image/upload/t_cover_big/co2tgb.jpg
                        if cover_id.startswith("//"):
                            # Replace size parameter with higher quality (t_1080p for larger, sharper images)
                            cover_url = f"https:{cover_id}".replace("t_thumb", "t_1080p").replace("t_cover_big", "t_1080p")
                        elif cover_id.startswith("http"):
                            # Already a full URL, upgrade quality
                            cover_url = cover_id.replace("t_thumb", "t_1080p").replace("t_cover_big", "t_1080p")
                        else:
                            # Just an ID, build the full URL with high quality
                            cover_url = f"https://images.igdb.com/igdb/image/upload/t_1080p/{cover_id}.jpg"
                
                # Format genres
                genres_str = ", ".join([g.get("name", "") for g in genres]) if isinstance(genres, list) else None
                
                # Format themes
                themes_str = ", ".join([t.get("name", "") for t in themes]) if isinstance(themes, list) else None
                
                # Format game modes
                game_modes_str = ", ".join([m.get("name", "") for m in game_modes]) if isinstance(game_modes, list) else None
                
                # Extract developers and publishers
                developers_list = []
                publishers_list = []
                if isinstance(involved_companies, list):
                    for ic in involved_companies:
                        company_name = ic.get("company", {}).get("name", "") if isinstance(ic.get("company"), dict) else ""
                        if company_name:
                            if ic.get("developer"):
                                developers_list.append(company_name)
                            if ic.get("publisher"):
                                publishers_list.append(company_name)
                developers_str = ", ".join(developers_list) if developers_list else None
                publishers_str = ", ".join(publishers_list) if publishers_list else None
                
                # Check if this IGDB ID already exists in another game
                existing_igdb = db.session.query(GameMaster).filter(
                    GameMaster.igdb_id == new_igdb_id,
                    GameMaster.game_id != game.game_id
                ).first()
                
                if existing_igdb:
                    self.log(f"  ⚠️  IGDB ID {new_igdb_id} already linked to '{existing_igdb.title}', skipping", "WARN")
                    self.stats["skipped"] += 1
                    continue
                
                # Update game
                game.igdb_id = new_igdb_id
                game.cover_url = cover_url
                game.genres = genres_str
                game.summary = summary
                game.rating = round(rating, 1) if rating else None
                game.total_rating = round(total_rating, 1) if total_rating else None
                game.total_rating_count = total_rating_count
                game.themes = themes_str
                game.game_modes = game_modes_str
                game.developers = developers_str
                game.publishers = publishers_str
                if first_release_date:
                    from datetime import datetime
                    game.first_release_date = datetime.fromtimestamp(first_release_date)
                
                db.session.add(game)
                self.stats["updated"] += 1
                
                self.log(f"  ✅ Updated: {igdb_name} (IGDB ID: {new_igdb_id})")
                
                # Commit in batches
                if i % batch_size == 0:
                    db.session.commit()
                    self.log(f"Committed {i} games...")
            
            except Exception as e:
                error_msg = str(e)
                # Check for duplicate IGDB ID (same game on multiple platforms)
                if "duplicate key" in error_msg and "igdb_id" in error_msg:
                    self.log(f"  ⚠️  Duplicate IGDB ID (game exists on another platform), skipping", "WARN")
                    self.stats["skipped"] += 1
                else:
                    self.log(f"  ❌ Error: {e}", "ERROR")
                    self.stats["failed"] += 1
                db.session.rollback()
        
        # Final commit
        db.session.commit()
        self.print_summary()
    
    def fetch_details_for_existing(self, batch_size: int = 100):
        """
        Fetch detailed metadata for games that already have IGDB IDs
        but are missing summary/rating/themes etc.
        """
        games = db.session.execute(
            db.text("""
                SELECT DISTINCT g.game_id, g.title, g.igdb_id
                FROM games_master g
                WHERE (
                    EXISTS (SELECT 1 FROM owned_games_steam WHERE game_id = g.game_id)
                    OR EXISTS (SELECT 1 FROM owned_games_epic WHERE game_id = g.game_id)
                    OR EXISTS (SELECT 1 FROM owned_games_gog WHERE game_id = g.game_id)
                )
                AND g.igdb_id IS NOT NULL
                AND g.summary IS NULL
                ORDER BY g.title
            """)
        ).fetchall()

        self.stats["total_games"] = len(games)
        self.log(f"Found {len(games)} owned games with IGDB IDs but missing details")

        if not games:
            self.log("All games already have full details!")
            return

        for i, (game_id, title, igdb_id) in enumerate(games, 1):
            try:
                self.log(f"[{i}/{len(games)}] Fetching details: {title} (IGDB: {igdb_id})")

                game = db.session.get(GameMaster, game_id)
                if not game:
                    continue

                # Fetch by IGDB ID directly (no fuzzy matching needed)
                result = self.igdb.get_game_by_igdb_id(igdb_id)

                if not result:
                    self.log(f"  ⚠️  No data returned from IGDB", "WARN")
                    self.stats["failed"] += 1
                    continue

                # Extract details
                summary = result.get("summary")
                rating = result.get("rating")
                total_rating = result.get("total_rating")
                total_rating_count = result.get("total_rating_count")
                themes = result.get("themes", [])
                game_modes = result.get("game_modes", [])
                involved_companies = result.get("involved_companies", [])
                genres = result.get("genres", [])

                # Format fields
                themes_str = ", ".join([t.get("name", "") for t in themes]) if isinstance(themes, list) else None
                game_modes_str = ", ".join([m.get("name", "") for m in game_modes]) if isinstance(game_modes, list) else None
                genres_str = ", ".join([g.get("name", "") for g in genres]) if isinstance(genres, list) else None

                developers_list = []
                publishers_list = []
                if isinstance(involved_companies, list):
                    for ic in involved_companies:
                        company_name = ic.get("company", {}).get("name", "") if isinstance(ic.get("company"), dict) else ""
                        if company_name:
                            if ic.get("developer"):
                                developers_list.append(company_name)
                            if ic.get("publisher"):
                                publishers_list.append(company_name)

                # Update game
                game.summary = summary
                game.rating = round(rating, 1) if rating else None
                game.total_rating = round(total_rating, 1) if total_rating else None
                game.total_rating_count = total_rating_count
                game.themes = themes_str
                game.game_modes = game_modes_str
                game.developers = ", ".join(developers_list) if developers_list else None
                game.publishers = ", ".join(publishers_list) if publishers_list else None

                # Update genres if missing
                if not game.genres and genres_str:
                    game.genres = genres_str

                # Update cover if missing
                cover_data = result.get("cover")
                if not game.cover_url and cover_data:
                    cover_id = cover_data.get("url") if isinstance(cover_data, dict) else cover_data
                    if cover_id:
                        if cover_id.startswith("//"):
                            game.cover_url = f"https:{cover_id}".replace("t_thumb", "t_1080p").replace("t_cover_big", "t_1080p")
                        elif cover_id.startswith("http"):
                            game.cover_url = cover_id.replace("t_thumb", "t_1080p").replace("t_cover_big", "t_1080p")

                db.session.add(game)
                self.stats["updated"] += 1
                self.log(f"  ✅ Updated details")

                if i % batch_size == 0:
                    db.session.commit()
                    self.log(f"Committed {i} games...")

            except Exception as e:
                self.log(f"  ❌ Error: {e}", "ERROR")
                self.stats["failed"] += 1
                db.session.rollback()

        db.session.commit()
        self.print_summary()

    def print_summary(self):
        """Print results summary."""
        print("\n" + "="*80)
        print("IGDB METADATA FETCH SUMMARY")
        print("="*80)
        print(f"Total games processed: {self.stats['total_games']}")
        print(f"✅ Updated with metadata: {self.stats['updated']}")
        print(f"⏭️  Skipped (duplicates): {self.stats['skipped']}")
        print(f"⚠️  Failed to match: {self.stats['failed']}")
        print("="*80 + "\n")
        
        if self.stats['updated'] > 0:
            print("✨ Cover art and metadata have been added!")
            print("Refresh your browser to see the changes: http://localhost:5000")
        else:
            print("No games were updated. Check for errors above.")


if __name__ == "__main__":
    try:
        fetcher = IGDBMetadataFetcher()
        
        if "--details" in sys.argv:
            # Fetch details for games that already have IGDB IDs
            fetcher.fetch_details_for_existing()
        else:
            # Fetch covers + details for games without IGDB IDs
            fetcher.fetch_and_update()
    except ValueError as e:
        print(f"❌ Error: {e}")
        print("\nMake sure your .env file has:")
        print("  IGDB_CLIENT_ID=your_client_id")
        print("  IGDB_ACCESS_TOKEN=your_access_token")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        sys.exit(1)
