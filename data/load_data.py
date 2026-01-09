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

def load_community_followers():
    conn = psycopg2.connect(**DB_CONFIG)
    df = pd.read_sql('SELECT "userId", "communityId" FROM community_follower WHERE "isActive"=true', conn)
    conn.close()
    return df
