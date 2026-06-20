"""Add gfn_game_id column for proper GeForce NOW deep linking

Revision ID: 8f3c4d9e2a1b
Revises: 72f65884cab5
Create Date: 2026-06-20 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8f3c4d9e2a1b'
down_revision = '72f65884cab5'
branch_labels = None
depends_on = None


def upgrade():
    # Add gfn_game_id column to gfn_games table
    op.add_column('gfn_games', sa.Column('gfn_game_id', sa.String(36), nullable=True))
    op.add_column('gfn_games', sa.Column('gfn_url', sa.String(255), nullable=True))
    
    # Update the view to use gfn_game_id for proper URLs
    op.execute('DROP VIEW IF EXISTS vw_owned_games_unified')
    
    op.execute("""
        CREATE VIEW vw_owned_games_unified AS
        -- Steam games
        SELECT 
            g.game_id,
            g.title,
            g.cover_url,
            g.genres,
            g.first_release_date,
            p.name as platform_name,
            a.username as account_username,
            og.steam_appid::TEXT as platform_specific_id,
            og.playtime_minutes,
            og.last_played,
            CASE WHEN gfn.game_id IS NOT NULL THEN true ELSE false END as is_on_gfn,
            COALESCE(
                CASE 
                    WHEN gfn.gfn_game_id IS NOT NULL 
                    THEN 'https://geforcenow.com/' || gfn.gfn_game_id
                    ELSE gfn.gfn_url
                END,
                NULL
            ) as gfn_deeplink_url
        FROM owned_games_steam og
        JOIN accounts a ON og.account_id = a.account_id
        JOIN platforms p ON a.platform_id = p.platform_id
        LEFT JOIN games_master g ON og.game_id = g.game_id
        LEFT JOIN gfn_games gfn ON g.game_id = gfn.game_id
        
        UNION ALL
        
        -- Epic games
        SELECT 
            g.game_id,
            g.title,
            g.cover_url,
            g.genres,
            g.first_release_date,
            p.name as platform_name,
            a.username as account_username,
            og.epic_item_id::TEXT as platform_specific_id,
            NULL as playtime_minutes,
            NULL as last_played,
            CASE WHEN gfn.game_id IS NOT NULL THEN true ELSE false END as is_on_gfn,
            COALESCE(
                CASE 
                    WHEN gfn.gfn_game_id IS NOT NULL 
                    THEN 'https://geforcenow.com/' || gfn.gfn_game_id
                    ELSE gfn.gfn_url
                END,
                NULL
            ) as gfn_deeplink_url
        FROM owned_games_epic og
        JOIN accounts a ON og.account_id = a.account_id
        JOIN platforms p ON a.platform_id = p.platform_id
        LEFT JOIN games_master g ON og.game_id = g.game_id
        LEFT JOIN gfn_games gfn ON g.game_id = gfn.game_id
        
        UNION ALL
        
        -- GOG games
        SELECT 
            g.game_id,
            g.title,
            g.cover_url,
            g.genres,
            g.first_release_date,
            p.name as platform_name,
            a.username as account_username,
            og.gog_product_id::TEXT as platform_specific_id,
            NULL as playtime_minutes,
            NULL as last_played,
            CASE WHEN gfn.game_id IS NOT NULL THEN true ELSE false END as is_on_gfn,
            COALESCE(
                CASE 
                    WHEN gfn.gfn_game_id IS NOT NULL 
                    THEN 'https://geforcenow.com/' || gfn.gfn_game_id
                    ELSE gfn.gfn_url
                END,
                NULL
            ) as gfn_deeplink_url
        FROM owned_games_gog og
        JOIN accounts a ON og.account_id = a.account_id
        JOIN platforms p ON a.platform_id = p.platform_id
        LEFT JOIN games_master g ON og.game_id = g.game_id
        LEFT JOIN gfn_games gfn ON g.game_id = gfn.game_id;
    """)


def downgrade():
    # Drop new columns
    op.drop_column('gfn_games', 'gfn_url')
    op.drop_column('gfn_games', 'gfn_game_id')
    
    # Recreate old view
    op.execute('DROP VIEW IF EXISTS vw_owned_games_unified')
    
    op.execute("""
        CREATE VIEW vw_owned_games_unified AS
        -- Steam games
        SELECT 
            g.game_id,
            g.title,
            g.cover_url,
            g.genres,
            g.first_release_date,
            p.name as platform_name,
            a.username as account_username,
            og.steam_appid::TEXT as platform_specific_id,
            og.playtime_minutes,
            og.last_played,
            CASE WHEN gfn.game_id IS NOT NULL THEN true ELSE false END as is_on_gfn,
            gfn.gfn_deeplink_url
        FROM owned_games_steam og
        JOIN accounts a ON og.account_id = a.account_id
        JOIN platforms p ON a.platform_id = p.platform_id
        LEFT JOIN games_master g ON og.game_id = g.game_id
        LEFT JOIN gfn_games gfn ON g.game_id = gfn.game_id
        
        UNION ALL
        
        -- Epic games
        SELECT 
            g.game_id,
            g.title,
            g.cover_url,
            g.genres,
            g.first_release_date,
            p.name as platform_name,
            a.username as account_username,
            og.epic_item_id::TEXT as platform_specific_id,
            NULL as playtime_minutes,
            NULL as last_played,
            CASE WHEN gfn.game_id IS NOT NULL THEN true ELSE false END as is_on_gfn,
            gfn.gfn_deeplink_url
        FROM owned_games_epic og
        JOIN accounts a ON og.account_id = a.account_id
        JOIN platforms p ON a.platform_id = p.platform_id
        LEFT JOIN games_master g ON og.game_id = g.game_id
        LEFT JOIN gfn_games gfn ON g.game_id = gfn.game_id
        
        UNION ALL
        
        -- GOG games
        SELECT 
            g.game_id,
            g.title,
            g.cover_url,
            g.genres,
            g.first_release_date,
            p.name as platform_name,
            a.username as account_username,
            og.gog_product_id::TEXT as platform_specific_id,
            NULL as playtime_minutes,
            NULL as last_played,
            CASE WHEN gfn.game_id IS NOT NULL THEN true ELSE false END as is_on_gfn,
            gfn.gfn_deeplink_url
        FROM owned_games_gog og
        JOIN accounts a ON og.account_id = a.account_id
        JOIN platforms p ON a.platform_id = p.platform_id
        LEFT JOIN games_master g ON og.game_id = g.game_id
        LEFT JOIN gfn_games gfn ON g.game_id = gfn.game_id;
    """)
