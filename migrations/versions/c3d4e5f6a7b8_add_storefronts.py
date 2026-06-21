"""Add EA, Battle.net, and Ubisoft storefronts

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-06-21 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'c3d4e5f6a7b8'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None


def upgrade():
    # Create new owned_games tables for EA, Battle.net, Ubisoft
    op.create_table(
        'owned_games_ea',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('game_id', sa.Integer(), nullable=True),
        sa.Column('ea_game_id', sa.String(100), nullable=False),
        sa.Column('added_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['account_id'], ['accounts.account_id'], ),
        sa.ForeignKeyConstraint(['game_id'], ['games_master.game_id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('account_id', 'ea_game_id', name='uq_ea_account_game')
    )

    op.create_table(
        'owned_games_battlenet',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('game_id', sa.Integer(), nullable=True),
        sa.Column('battlenet_game_id', sa.String(100), nullable=False),
        sa.Column('added_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['account_id'], ['accounts.account_id'], ),
        sa.ForeignKeyConstraint(['game_id'], ['games_master.game_id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('account_id', 'battlenet_game_id', name='uq_battlenet_account_game')
    )

    op.create_table(
        'owned_games_ubisoft',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('game_id', sa.Integer(), nullable=True),
        sa.Column('ubisoft_game_id', sa.String(100), nullable=False),
        sa.Column('added_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['account_id'], ['accounts.account_id'], ),
        sa.ForeignKeyConstraint(['game_id'], ['games_master.game_id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('account_id', 'ubisoft_game_id', name='uq_ubisoft_account_game')
    )

    # Recreate view to include all platforms
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
        LEFT JOIN gfn_games gfn ON g.game_id = gfn.game_id

        UNION ALL

        SELECT 
            g.game_id, g.title, g.cover_url, g.genres, g.first_release_date,
            g.total_rating, g.status,
            p.name as platform_name, a.username as account_username,
            og.ea_game_id::TEXT as platform_specific_id,
            NULL as playtime_minutes, NULL as last_played,
            CASE WHEN gfn.game_id IS NOT NULL THEN true ELSE false END as is_on_gfn,
            COALESCE(
                CASE WHEN gfn.gfn_game_id IS NOT NULL 
                     THEN 'https://play.geforcenow.com/games?game-id=' || gfn.gfn_game_id
                     ELSE gfn.gfn_url END,
                NULL
            ) as gfn_deeplink_url
        FROM owned_games_ea og
        JOIN accounts a ON og.account_id = a.account_id
        JOIN platforms p ON a.platform_id = p.platform_id
        LEFT JOIN games_master g ON og.game_id = g.game_id
        LEFT JOIN gfn_games gfn ON g.game_id = gfn.game_id

        UNION ALL

        SELECT 
            g.game_id, g.title, g.cover_url, g.genres, g.first_release_date,
            g.total_rating, g.status,
            p.name as platform_name, a.username as account_username,
            og.battlenet_game_id::TEXT as platform_specific_id,
            NULL as playtime_minutes, NULL as last_played,
            CASE WHEN gfn.game_id IS NOT NULL THEN true ELSE false END as is_on_gfn,
            COALESCE(
                CASE WHEN gfn.gfn_game_id IS NOT NULL 
                     THEN 'https://play.geforcenow.com/games?game-id=' || gfn.gfn_game_id
                     ELSE gfn.gfn_url END,
                NULL
            ) as gfn_deeplink_url
        FROM owned_games_battlenet og
        JOIN accounts a ON og.account_id = a.account_id
        JOIN platforms p ON a.platform_id = p.platform_id
        LEFT JOIN games_master g ON og.game_id = g.game_id
        LEFT JOIN gfn_games gfn ON g.game_id = gfn.game_id

        UNION ALL

        SELECT 
            g.game_id, g.title, g.cover_url, g.genres, g.first_release_date,
            g.total_rating, g.status,
            p.name as platform_name, a.username as account_username,
            og.ubisoft_game_id::TEXT as platform_specific_id,
            NULL as playtime_minutes, NULL as last_played,
            CASE WHEN gfn.game_id IS NOT NULL THEN true ELSE false END as is_on_gfn,
            COALESCE(
                CASE WHEN gfn.gfn_game_id IS NOT NULL 
                     THEN 'https://play.geforcenow.com/games?game-id=' || gfn.gfn_game_id
                     ELSE gfn.gfn_url END,
                NULL
            ) as gfn_deeplink_url
        FROM owned_games_ubisoft og
        JOIN accounts a ON og.account_id = a.account_id
        JOIN platforms p ON a.platform_id = p.platform_id
        LEFT JOIN games_master g ON og.game_id = g.game_id
        LEFT JOIN gfn_games gfn ON g.game_id = gfn.game_id;
    """)


def downgrade():
    op.execute('DROP VIEW IF EXISTS vw_owned_games_unified')

    op.drop_table('owned_games_ubisoft')
    op.drop_table('owned_games_battlenet')
    op.drop_table('owned_games_ea')

    # Recreate view without new storefronts
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
        FROM owned_games_steam og JOIN accounts a ON og.account_id = a.account_id JOIN platforms p ON a.platform_id = p.platform_id LEFT JOIN games_master g ON og.game_id = g.game_id LEFT JOIN gfn_games gfn ON g.game_id = gfn.game_id
        UNION ALL
        SELECT g.game_id, g.title, g.cover_url, g.genres, g.first_release_date, g.total_rating, g.status, p.name, a.username, og.epic_item_id::TEXT, NULL, NULL, CASE WHEN gfn.game_id IS NOT NULL THEN true ELSE false END, COALESCE(CASE WHEN gfn.gfn_game_id IS NOT NULL THEN 'https://play.geforcenow.com/games?game-id=' || gfn.gfn_game_id ELSE gfn.gfn_url END, NULL)
        FROM owned_games_epic og JOIN accounts a ON og.account_id = a.account_id JOIN platforms p ON a.platform_id = p.platform_id LEFT JOIN games_master g ON og.game_id = g.game_id LEFT JOIN gfn_games gfn ON g.game_id = gfn.game_id
        UNION ALL
        SELECT g.game_id, g.title, g.cover_url, g.genres, g.first_release_date, g.total_rating, g.status, p.name, a.username, og.gog_product_id::TEXT, NULL, NULL, CASE WHEN gfn.game_id IS NOT NULL THEN true ELSE false END, COALESCE(CASE WHEN gfn.gfn_game_id IS NOT NULL THEN 'https://play.geforcenow.com/games?game-id=' || gfn.gfn_game_id ELSE gfn.gfn_url END, NULL)
        FROM owned_games_gog og JOIN accounts a ON og.account_id = a.account_id JOIN platforms p ON a.platform_id = p.platform_id LEFT JOIN games_master g ON og.game_id = g.game_id LEFT JOIN gfn_games gfn ON g.game_id = gfn.game_id;
    """)
