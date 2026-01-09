import psycopg2
import json
import uuid
import random
from datetime import datetime, timedelta
from psycopg2.extras import execute_batch, Json
from config import DB_CONFIG

# ================= CONFIG =================
TOTAL_FANS = 500
POST_PER_USER = (2, 6)
FOLLOW_RATE = 0.6
UNFOLLOW_POST_RATE = 0.1

START_DATE = datetime(2023, 1, 1)
END_DATE = datetime(2025, 1, 1)

AVATAR = "https://i.pravatar.cc/300?img={}"
BG = "https://picsum.photos/1200/400?random={}"
TAGS_POOL = ["music", "gaming", "concert", "behind_the_scene", "fan_meet"]

# ================= UTILS =================
def random_datetime():
    delta = END_DATE - START_DATE
    return START_DATE + timedelta(
        seconds=random.randint(0, int(delta.total_seconds()))
    )

# ================= LOAD JSON =================
with open("communities.json") as f:
    communities = json.load(f)

with open("idols.json") as f:
    idols = json.load(f)

# ================= DB =================
conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor()

cur.execute("""
SELECT
  current_database(),
  current_schema(),
  inet_server_addr(),
  inet_server_port();
""")
print("🔍 DB INFO:", cur.fetchone())
# =====================================================
# 1️⃣ COMMUNITY
# =====================================================
community_rows = []
community_id_map = {}

for c in communities:
    cid = str(uuid.uuid4())
    t = random_datetime()

    community_id_map[c["name"]] = cid

    community_rows.append((
        cid, c["name"], c["communityType"],
        AVATAR.format(random.randint(1, 70)),
        BG.format(random.randint(1, 1000)),
        t, t
    ))

execute_batch(cur, """
INSERT INTO community (
    id, name, community_type,
    avatar_url, background_url,
    "createdAt", "updatedAt"
)
VALUES (%s,%s,%s,%s,%s,%s,%s)
""", community_rows)

print(f"✅ Communities: {len(community_rows)}")

# =====================================================
# 2️⃣ USER (IDOL)
# =====================================================
user_rows = []
idol_user_ids = []
seen_stage = set()

for idol in idols:
    stage = idol["stageName"].strip()
    if stage in seen_stage:
        continue
    seen_stage.add(stage)

    uid = str(uuid.uuid4())
    t = random_datetime()

    community_name = next(
        c["name"] for c in communities
        if c["id"] == idol["communityId"]
    )

    user_rows.append((
        uid,
        f"{stage.lower()}@idol.com",
        stage.lower(),
        "hashed_password",
        "IDOL",
        AVATAR.format(random.randint(1, 70)),
        BG.format(random.randint(1, 1000)),
        community_id_map[community_name],
        t, t
    ))

    idol_user_ids.append(uid)

execute_batch(cur, """
INSERT INTO "user" (
    id, email, username, password, role,
    avatar_url, background_url,
    "communityId",
    "createdAt", "updatedAt"
)
VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
""", user_rows)

print(f"✅ Idols: {len(idol_user_ids)}")

# =====================================================
# 3️⃣ USER (FAN) – EMAIL UNIQUE
# =====================================================
fan_user_ids = []
fan_rows = []

for i in range(TOTAL_FANS):
    uid = str(uuid.uuid4())
    t = random_datetime()

    fan_rows.append((
        uid,
        f"fan_{uid[:8]}@mail.com",  # 🔒 UNIQUE
        f"fan_{i}",
        "hashed_password",
        "FAN",
        AVATAR.format(random.randint(1, 70)),
        None,
        None,
        t, t
    ))
    fan_user_ids.append(uid)

execute_batch(cur, """
INSERT INTO "user" (
    id, email, username, password, role,
    avatar_url, background_url,
    "communityId",
    "createdAt", "updatedAt"
)
VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
""", fan_rows)

print(f"✅ Fans: {len(fan_user_ids)}")

# =====================================================
# 4️⃣ COMMUNITY_FOLLOWER
# =====================================================
follower_rows = []

for fan_id in fan_user_ids:
    for cid in community_id_map.values():
        if random.random() < FOLLOW_RATE:
            t = random_datetime()
            follower_rows.append((
                str(uuid.uuid4()),
                True,
                t, t,
                0, False, None,
                Json({}),
                fan_id,
                cid
            ))

execute_batch(cur, """
INSERT INTO community_follower (
    id, "isActive", "createdAt", "updatedAt",
    version, is_deleted, deleted_at,
    metadata, "userId", "communityId"
)
VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
""", follower_rows)

print(f"✅ Community Followers: {len(follower_rows)}")

# =====================================================
# 5️⃣ POST (IDOL + FAN)
# =====================================================
post_rows = []
all_users = idol_user_ids + fan_user_ids
all_communities = list(community_id_map.values())

for uid in all_users:
    for _ in range(random.randint(*POST_PER_USER)):
        t = random_datetime()

        if random.random() < UNFOLLOW_POST_RATE:
            cid = random.choice(all_communities)
        else:
            cid = random.choice(all_communities)

        post_rows.append((
            str(uuid.uuid4()),
            f"Post by user {uid[:6]}",
            Json({"tags": random.sample(TAGS_POOL, random.randint(1, 3))}),
            uid,
            cid,
            t, t
        ))

execute_batch(cur, """
INSERT INTO post (
    id, content, metadata,
    "authorId", "communityId",
    "createdAt", "updatedAt"
)
VALUES (%s,%s,%s,%s,%s,%s,%s)
""", post_rows)

print(f"✅ Posts: {len(post_rows)}")

# =====================================================
# 6️⃣ INTERACTION (VIEW / LIKE / COMMENT)
# =====================================================
VIEW_RANGE = (5, 25)
LIKE_RATIO = (0.1, 0.3)
COMMENT_RATIO = (0.05, 0.15)

IDOL_VIEW_RATIO = 0.3
IDOL_LIKE_BOOST = 1.5
IDOL_COMMENT_BOOST = 2.0

view_rows = []
like_rows = []
comment_rows = []

idol_set = set(idol_user_ids)
fan_set = set(fan_user_ids)

print("🚀 Seeding interactions...")

for post_id, _, _, author_id, _, post_created_at, _ in post_rows:
    # -----------------
    # VIEWERS
    # -----------------
    view_count = random.randint(*VIEW_RANGE)

    idol_views = int(view_count * IDOL_VIEW_RATIO)
    fan_views = view_count - idol_views

    viewers = set()
    viewers.update(random.sample(idol_user_ids, min(idol_views, len(idol_user_ids))))
    viewers.update(random.sample(fan_user_ids, min(fan_views, len(fan_user_ids))))

    for uid in viewers:
        t = post_created_at + timedelta(
            minutes=random.randint(1, 60 * 24 * 30)
        )
        view_rows.append((
            str(uuid.uuid4()),
            post_id,
            uid,
            t, t
        ))

    # -----------------
    # LIKES
    # -----------------
    for uid in viewers:
        prob = random.uniform(*LIKE_RATIO)
        if uid in idol_set:
            prob *= IDOL_LIKE_BOOST

        if random.random() < min(prob, 1.0):
            t = post_created_at + timedelta(
                minutes=random.randint(1, 60 * 24 * 30)
            )
            like_rows.append((
                str(uuid.uuid4()),
                post_id,
                uid,
                t, t
            ))

    # -----------------
    # COMMENTS
    # -----------------
    for uid in viewers:
        prob = random.uniform(*COMMENT_RATIO)
        if uid in idol_set:
            prob *= IDOL_COMMENT_BOOST

        if random.random() < min(prob, 1.0):
            t = post_created_at + timedelta(
                minutes=random.randint(1, 60 * 24 * 30)
            )
            comment_rows.append((
                str(uuid.uuid4()),
                f"Comment by {uid[:6]}",
                post_id,
                uid,
                t, t
            ))

# =====================
# INSERT BATCH
# =====================
print("💾 Inserting post_view...")
execute_batch(cur, """
INSERT INTO post_view (
    id, "postId", "userId",
    "createdAt", "updatedAt"
)
VALUES (%s,%s,%s,%s,%s)
""", view_rows, page_size=1000)

print("💾 Inserting post_like...")
execute_batch(cur, """
INSERT INTO post_like (
    id, "postId", "userId",
    "createdAt", "updatedAt"
)
VALUES (%s,%s,%s,%s,%s)
""", like_rows, page_size=1000)

print("💾 Inserting comment...")
execute_batch(cur, """
INSERT INTO comment (
    id, content,
    "postId", "userId",
    "createdAt", "updatedAt"
)
VALUES (%s,%s,%s,%s,%s,%s)
""", comment_rows, page_size=1000)

print(f"👀 Views: {len(view_rows)}")
print(f"❤️ Likes: {len(like_rows)}")
print(f"💬 Comments: {len(comment_rows)}")

# 🔥 BẮT BUỘC
conn.commit()

cur.close()
conn.close()

print("🎉 FULL SEED COMPLETED SUCCESSFULLY")