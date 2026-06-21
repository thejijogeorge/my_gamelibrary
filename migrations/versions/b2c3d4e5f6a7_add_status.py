"""Add game status column and update view

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-21 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    # Add status column with default
    op.add_column('games_master', sa.Column('status', sa.String(20), nullable=False, server_default='Not Started'))

    # Recreate view to include status
    op.execute('DROP VIEW IF EXISTS vw_owned_games_unified')

    op.execute("""
        CREATE VIEW vw_owned_games_unified AS
        SELECT 
            g.game_id, g.title, g.cover_url, g.genres, g.first_release_date,
            g.total_rating, g.status,
            p.name as platform_name, a.username as account_username,
            og.steam_appid::TEXT as platform_specific_id,
            og.playtime_minutes, og.last_played,
            CASE WHEN gfn.game_id IS NOT NULL THEN true ELSE false END as is_on_gfn,
            COALESCE(
                CASE WHEN gfn.gfn_game_id IS NOT NULL 
                     THEN 'https://play.geforcenow.com/games?game-id=' || gfn.gfn_game_id
                     ELSE gfn.gfn_url END,
                NULL
            ) as gfn_deeplink_url
        FROM owned_games_steam og
        JOIN accounts a ON og.account_id = a.account_id
        JOIN platforms p ON a.platform_id = p.platform_id
        LEFT JOIN games_master g ON og.game_id = g.game_id
        LEFT JOIN gfn_games gfn ON g.game_id = gfn.game_id

        UNION ALL

        SELECT 
            g.game_id, g.title, g.cover_url, g.genres, g.first_release_date,
            g.total_rating, g.status,
            p.name as platform_name, a.username as account_username,
            og.epic_item_id::TEXT as platform_specific_id,
            NULL as playtime_minutes, NULL as last_played,
            CASE WHEN gfn.game_id IS NOT NULL THEN true ELSE false END as is_on_gfn,
            COALESCE(
                CASE WHEN gfn.gfn_game_id IS NOT NULL 
                     THEN 'https://play.geforcenow.com/games?game-id=' || gfn.gfn_game_id
                     ELSE gfn.gfn_url END,
                NULL
            ) as gfn_deeplink_url
        FROM owned_games_epic og
        JOIN accounts a ON og.account_id = a.account_id
        JOIN platforms p ON a.platform_id = p.platform_id
        LEFT JOIN games_master g ON og.game_id = g.game_id
        LEFT JOIN gfn_games gfn ON g.game_id = gfn.game_id

        UNION ALL

        SELECT 
            g.game_id, g.title, g.cover_url, g.genres, g.first_release_date,
            g.total_rating, g.status,
            p.name as platform_name, a.username as account_username,
            og.gog_product_id::TEXT as platform_specific_id,
            NULL as playtime_minutes, NULL as last_played,
            CASE WHEN gfn.game_id IS NOT NULL THEN true ELSE false END as is_on_gfn,
            COALESCE(
                CASE WHEN gfn.gfn_game_id IS NOT NULL 
                     THEN 'https://play.geforcenow.com/games?game-id=' || gfn.gfn_game_id
                     ELSE gfn.gfn_url END,
                NULL
            ) as gfn_deeplink_url
        FROM owned_games_gog og
        JOIN accounts a ON og.account_id = a.account_id
        JOIN platforms p ON a.platform_id = p.platform_id
        LEFT JOIN games_master g ON og.game_id = g.game_id
        LEFT JOIN gfn_games gfn ON g.game_id = gfn.game_id;
    """)


def downgrade():
    op.drop_column('games_master', 'status')

    op.execute('DROP VIEW IF EXISTS vw_owned_games_unified')

    op.execute("""
        CREATE VIEW vw_owned_games_unified AS
        SELECT 
            g.game_id, g.title, g.cover_url, g.genres, g.first_release_date,
            p.name as platform_name, a.username as account_username,
            og.steam_appid::TEXT as platform_specific_id,
            og.playtime_minutes, og.last_played,
            CASE WHEN gfn.game_id IS NOT NULL THEN true ELSE false END as is_on_gfn,
            COALESCE(CASE WHEN gfn.gfn_game_id IS NOT NULL THEN 'https://geforcenow.com/' || gfn.gfn_game_id ELSE gfn.gfn_url END, NULL) as gfn_deeplink_url
        FROM owned_games_steam og JOIN accounts a ON og.account_id = a.account_id JOIN platforms p ON a.platform_id = p.platform_id LEFT JOIN games_master g ON og.game_id = g.game_id LEFT JOIN gfn_games gfn ON g.game_id = gfn.game_id
        UNION ALL
        SELECT g.game_id, g.title, g.cover_url, g.genres, g.first_release_date, p.name, a.username, og.epic_item_id::TEXT, NULL, NULL, CASE WHEN gfn.game_id IS NOT NULL THEN true ELSE false END, COALESCE(CASE WHEN gfn.gfn_game_id IS NOT NULL THEN 'https://geforcenow.com/' || gfn.gfn_game_id ELSE gfn.gfn_url END, NULL)
        FROM owned_games_epic og JOIN accounts a ON og.account_id = a.account_id JOIN platforms p ON a.platform_id = p.platform_id LEFT JOIN games_master g ON og.game_id = g.game_id LEFT JOIN gfn_games gfn ON g.game_id = gfn.game_id
        UNION ALL
        SELECT g.game_id, g.title, g.cover_url, g.genres, g.first_release_date, p.name, a.username, og.gog_product_id::TEXT, NULL, NULL, CASE WHEN gfn.game_id IS NOT NULL THEN true ELSE false END, COALESCE(CASE WHEN gfn.gfn_game_id IS NOT NULL THEN 'https://geforcenow.com/' || gfn.gfn_game_id ELSE gfn.gfn_url END, NULL)
        FROM owned_games_gog og JOIN accounts a ON og.account_id = a.account_id JOIN platforms p ON a.platform_id = p.platform_id LEFT JOIN games_master g ON og.game_id = g.game_id LEFT JOIN gfn_games gfn ON g.game_id = gfn.game_id;
    """)
