import pandas as pd
from config import DB_CONFIG
import psycopg2
from lightfm.data import Dataset


def load_users():
    conn = psycopg2.connect(**DB_CONFIG)
    df = pd.read_sql('SELECT id, role FROM "user"', conn)
    conn.close()
    return df


def load_posts():
    conn = psycopg2.connect(**DB_CONFIG)
    df = pd.read_sql('SELECT id, metadata, "communityId" FROM post', conn)
    conn.close()
    return df


def load_posts_with_engagement():
    """
    Load posts with engagement metrics and recency data for cold-start recommendations.
    Returns posts with: id, metadata, communityId, createdAt, view_count, like_count, comment_count
    """
    conn = psycopg2.connect(**DB_CONFIG)
    df = pd.read_sql('''
        SELECT
            id,
            metadata,
            "communityId",
            "createdAt",
            view_count,
            like_count,
            comment_count
        FROM post
    ''', conn)
    conn.close()
    return df


def load_interactions():
    conn = psycopg2.connect(**DB_CONFIG)
    # Load interactions - renamed columns to match expected format
    df_interactions = pd.read_sql("""
        SELECT "userId" as user_id, "postId" as post_id, 'view' AS type FROM post_view
        UNION ALL
        SELECT "userId" as user_id, "postId" as post_id, 'like' FROM post_like
        UNION ALL
        SELECT "userId" as user_id, "postId" as post_id, 'comment' FROM comment
    """, conn)
    conn.close()

    return df_interactions


def load_user_interaction_counts():
    """
    Load interaction count per user for cold-start detection.
    Returns DataFrame with: user_id, interaction_count
    """
    conn = psycopg2.connect(**DB_CONFIG)
    df = pd.read_sql("""
        SELECT user_id, COUNT(*) as interaction_count FROM (
            SELECT "userId" as user_id FROM post_view
            UNION ALL
            SELECT "userId" as user_id FROM post_like
            UNION ALL
            SELECT "userId" as user_id FROM comment
        ) interactions
        GROUP BY user_id
    """, conn)
    conn.close()
    return df


def load_community_followers():
    conn = psycopg2.connect(**DB_CONFIG)
    df = pd.read_sql('SELECT "userId", "communityId" FROM community_follower WHERE "isActive"=true', conn)
    conn.close()
    return df


def load_communities():
    """
    Load community metadata for content similarity computation.
    Returns DataFrame with: id, name, community_type
    """
    conn = psycopg2.connect(**DB_CONFIG)
    df = pd.read_sql('SELECT id, name, community_type FROM community', conn)
    conn.close()
    return df


def load_community_dominant_tags():
    """
    Load dominant tags per community based on post tag frequency.
    Returns DataFrame with: communityId, tag, tag_count
    """
    conn = psycopg2.connect(**DB_CONFIG)
    # Extract tags from metadata JSON and count occurrences per community
    df = pd.read_sql("""
        WITH post_tags AS (
            SELECT
                "communityId",
                jsonb_array_elements_text(metadata->'tags') as tag
            FROM post
            WHERE metadata ? 'tags'
        )
        SELECT
            "communityId",
            tag,
            COUNT(*) as tag_count
        FROM post_tags
        GROUP BY "communityId", tag
        ORDER BY "communityId", tag_count DESC
    """, conn)
    conn.close()
    return df


def check_user_exists(user_id: str) -> bool:
    """
    Check if a user exists in the database (real-time check).
    Used to verify new users created after service startup.

    Args:
        user_id: User ID to check

    Returns:
        True if user exists, False otherwise
    """
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM "user" WHERE id = %s LIMIT 1', (user_id,))
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return result is not None


def load_user_followed_communities(user_id: str) -> list:
    """
    Load communities followed by a specific user (real-time check).
    Used for new users created after service startup.

    Args:
        user_id: User ID

    Returns:
        List of community IDs the user follows
    """
    conn = psycopg2.connect(**DB_CONFIG)
    df = pd.read_sql(
        'SELECT "communityId" FROM community_follower WHERE "userId" = %s AND "isActive" = true',
        conn,
        params=(user_id,)
    )
    conn.close()
    return df['communityId'].tolist()
