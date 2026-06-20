"""unified owned games view

Revision ID: 72f65884cab5
Revises: 2d802ec2e524
Create Date: 2026-06-20 03:46:48.497712

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '72f65884cab5'
down_revision = '2d802ec2e524'
branch_labels = None
depends_on = None


VIEW_SQL = """
CREATE VIEW vw_owned_games_unified AS
SELECT
    gm.game_id,
    gm.title,
    gm.cover_url,
    p.name AS platform_name,
    a.username AS account_username,
    os.steam_appid::text AS platform_specific_id,
    os.playtime_minutes,
    os.last_played,
    (gfn.id IS NOT NULL) AS is_on_gfn,
    gfn.gfn_deeplink_url
FROM owned_games_steam os
JOIN accounts a ON a.account_id = os.account_id
JOIN platforms p ON p.platform_id = a.platform_id
LEFT JOIN games_master gm ON gm.game_id = os.game_id
LEFT JOIN gfn_games gfn ON gfn.game_id = os.game_id

UNION ALL

SELECT
    gm.game_id,
    gm.title,
    gm.cover_url,
    p.name AS platform_name,
    a.username AS account_username,
    oe.epic_item_id AS platform_specific_id,
    NULL AS playtime_minutes,
    NULL AS last_played,
    (gfn.id IS NOT NULL) AS is_on_gfn,
    gfn.gfn_deeplink_url
FROM owned_games_epic oe
JOIN accounts a ON a.account_id = oe.account_id
JOIN platforms p ON p.platform_id = a.platform_id
LEFT JOIN games_master gm ON gm.game_id = oe.game_id
LEFT JOIN gfn_games gfn ON gfn.game_id = oe.game_id

UNION ALL

SELECT
    gm.game_id,
    gm.title,
    gm.cover_url,
    p.name AS platform_name,
    a.username AS account_username,
    og.gog_product_id AS platform_specific_id,
    NULL AS playtime_minutes,
    NULL AS last_played,
    (gfn.id IS NOT NULL) AS is_on_gfn,
    gfn.gfn_deeplink_url
FROM owned_games_gog og
JOIN accounts a ON a.account_id = og.account_id
JOIN platforms p ON p.platform_id = a.platform_id
LEFT JOIN games_master gm ON gm.game_id = og.game_id
LEFT JOIN gfn_games gfn ON gfn.game_id = og.game_id;
"""


def upgrade():
    # Views aren't tracked by Alembic autogenerate, so this is hand-written.
    # Unions the three platform-specific owned_games_* tables into one queryable
    # shape — this is what the Flask routes/htmx filtering will read from,
    # so adding platform #4 later never touches the query layer.
    op.execute(VIEW_SQL)


def downgrade():
    op.execute("DROP VIEW IF EXISTS vw_owned_games_unified;")
