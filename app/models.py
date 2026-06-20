from datetime import datetime

from app import db


class Platform(db.Model):
    """Seed data: Steam, Epic, GOG. Add a row here when you add a new
    storefront — nothing else in this table changes."""

    __tablename__ = "platforms"

    platform_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)

    accounts = db.relationship("Account", back_populates="platform")

    def __repr__(self):
        return f"<Platform {self.name}>"


class Account(db.Model):
    """One row per username you have on a given platform. Supports
    multiple usernames per platform (e.g. two Steam accounts)."""

    __tablename__ = "accounts"
    __table_args__ = (
        db.UniqueConstraint("platform_id", "username", name="uq_account_platform_username"),
    )

    account_id = db.Column(db.Integer, primary_key=True)
    platform_id = db.Column(db.Integer, db.ForeignKey("platforms.platform_id"), nullable=False)
    username = db.Column(db.String(100), nullable=False)
    display_name = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    platform = db.relationship("Platform", back_populates="accounts")

    def __repr__(self):
        return f"<Account {self.username} on platform {self.platform_id}>"


class GameMaster(db.Model):
    """The canonical game list, pulled from IGDB. Every platform-specific
    owned-game row points here via game_id — this is what lets the
    frontend treat 'Hades' as one game regardless of which storefront(s)
    it came from."""

    __tablename__ = "games_master"

    game_id = db.Column(db.Integer, primary_key=True)
    igdb_id = db.Column(db.Integer, unique=True, nullable=True)
    title = db.Column(db.String(255), nullable=False, index=True)
    slug = db.Column(db.String(255), nullable=True)
    cover_url = db.Column(db.String(500), nullable=True)
    first_release_date = db.Column(db.Date, nullable=True)
    genres = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<GameMaster {self.title}>"


class OwnedGameSteam(db.Model):
    __tablename__ = "owned_games_steam"
    __table_args__ = (
        db.UniqueConstraint("account_id", "steam_appid", name="uq_steam_account_appid"),
    )

    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.account_id"), nullable=False)
    # Nullable: a game can be ingested before the IGDB matcher has run on it.
    game_id = db.Column(db.Integer, db.ForeignKey("games_master.game_id"), nullable=True)
    steam_appid = db.Column(db.Integer, nullable=False)
    playtime_minutes = db.Column(db.Integer, default=0)
    last_played = db.Column(db.DateTime, nullable=True)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)

    account = db.relationship("Account")
    game = db.relationship("GameMaster")


class OwnedGameEpic(db.Model):
    __tablename__ = "owned_games_epic"
    __table_args__ = (
        db.UniqueConstraint("account_id", "epic_item_id", name="uq_epic_account_item"),
    )

    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.account_id"), nullable=False)
    game_id = db.Column(db.Integer, db.ForeignKey("games_master.game_id"), nullable=True)
    epic_namespace = db.Column(db.String(100), nullable=True)
    epic_item_id = db.Column(db.String(100), nullable=False)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)

    account = db.relationship("Account")
    game = db.relationship("GameMaster")


class OwnedGameGog(db.Model):
    __tablename__ = "owned_games_gog"
    __table_args__ = (
        db.UniqueConstraint("account_id", "gog_product_id", name="uq_gog_account_product"),
    )

    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.account_id"), nullable=False)
    game_id = db.Column(db.Integer, db.ForeignKey("games_master.game_id"), nullable=True)
    gog_product_id = db.Column(db.String(100), nullable=False)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)

    account = db.relationship("Account")
    game = db.relationship("GameMaster")


class GfnGame(db.Model):
    """Full GeForce Now catalog. One row per game, with flags for which
    storefront(s) carry the GFN-playable version, plus the deep link to
    launch streaming directly."""

    __tablename__ = "gfn_games"

    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.Integer, db.ForeignKey("games_master.game_id"), unique=True, nullable=False)
    available_on_steam = db.Column(db.Boolean, default=False)
    available_on_epic = db.Column(db.Boolean, default=False)
    available_on_gog = db.Column(db.Boolean, default=False)
    gfn_deeplink_url = db.Column(db.String(500), nullable=True)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)

    game = db.relationship("GameMaster")
