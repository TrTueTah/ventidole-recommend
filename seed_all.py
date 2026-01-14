import psycopg2
import json
import uuid
import random
import math
from datetime import datetime, timedelta
from collections import defaultdict
from psycopg2.extras import execute_batch, Json
from config import DB_CONFIG

# =====================================================
# CONFIG
# =====================================================
TOTAL_FANS = 500
FOLLOW_RATE = 0.6

POST_RANGE_IDOL = (20, 40)
POST_RANGE_FAN = (1, 5)

NOISE_POST_RATE = 0.1
NOISE_INTERACTION_RATE = 0.05

# -------- TIME CONFIG (LAST 6 MONTHS + RECENCY BIAS)
END_DATE = datetime.now()
START_DATE = END_DATE - timedelta(days=180)

RECENCY_LAMBDA_IDOL = 0.12
RECENCY_LAMBDA_FAN = 0.06
INTERACTION_LAMBDA = 0.25  # strong recency for interaction

VIEW_RANGE = (5, 25)
LIKE_RATIO = (0.1, 0.3)
COMMENT_RATIO = (0.05, 0.15)

IDOL_LIKE_BOOST = 1.5
IDOL_COMMENT_BOOST = 2.0

AVATAR = "https://i.pravatar.cc/300?img={}"
BG = "https://picsum.photos/1200/400?random={}"
POST_IMAGE = "https://picsum.photos/800/600?random={}"

POST_IMAGE_RATE = 0.8

# =====================================================
# TAG SYSTEM (USER FRIENDLY)
# =====================================================
TAG_CATALOG = {
    "content": ["discussion", "fan_content", "announcement", "media"],
    "theme": [
        "music", "kpop", "dance", "vocal",
        "choreography", "behind_the_scene",
        "daily_life", "collab"
    ],
    "mood": ["hype", "emotional", "funny", "wholesome", "serious"],
    "event": ["concert", "fan_meet", "release", "practice"]
}

# =====================================================
# CONTENT TEMPLATES
# =====================================================
POST_TEMPLATES = {
    "discussion": [
        "What do you think about {topic}?",
        "Let's discuss about {topic}",
        "Any thoughts on {topic}?"
    ],
    "fan_content": [
        "Fan art inspired by {topic}",
        "I made this for {topic}",
        "Sharing my fan content about {topic}"
    ],
    "announcement": [
        "Official announcement regarding {topic}",
        "Important update about {topic}"
    ],
    "daily_life": [
        "A day in my life",
        "Sharing some daily moments",
        "Daily life lately"
    ],
    "dance": [
        "Dance practice today",
        "Trying new choreography",
        "Dance cover rehearsal"
    ],
    "music": [
        "Listening to music lately",
        "Working on new music",
        "Music that inspires me"
    ],
    "behind_the_scene": [
        "Behind the scene moments",
        "Backstage vibes",
        "Unseen moments from practice"
    ],
    "collab": [
        "Collaboration in progress",
        "Working with amazing people",
        "New collab coming soon"
    ]
}

MICRO_NOISE = ["", " ✨", " 💙", " 🎶", " today", " lately", " lately 😊"]

# =====================================================
# UTILS (RECENCY BIAS)
# =====================================================
def random_datetime_recency(lambda_val):
    max_days = (END_DATE - START_DATE).days
    u = random.random()
    age_days = -math.log(1 - u) / lambda_val
    age_days = min(age_days, max_days)
    return END_DATE - timedelta(days=age_days)

def interaction_datetime(post_time):
    u = random.random()
    age_hours = -math.log(1 - u) / INTERACTION_LAMBDA
    t = post_time + timedelta(hours=age_hours)
    return min(t, datetime.now())

def post_range(uid, idol_set):
    return POST_RANGE_IDOL if uid in idol_set else POST_RANGE_FAN

def sample_tags():
    tags = [random.choice(TAG_CATALOG["content"])]
    tags.extend(random.sample(TAG_CATALOG["theme"], random.randint(1, 2)))

    if random.random() < 0.4:
        tags.append(random.choice(TAG_CATALOG["mood"]))
    if random.random() < 0.2:
        tags.append(random.choice(TAG_CATALOG["event"]))

    return list(set(tags))

def generate_post_content(tags):
    primary = random.choice(tags)
    template = random.choice(
        POST_TEMPLATES.get(primary, ["Sharing something about {topic}"])
    )
    return template.format(topic=primary.replace("_", " ")) + random.choice(MICRO_NOISE)

# =====================================================
# LOAD DATA
# =====================================================
with open("communities.json") as f:
    communities = json.load(f)

with open("idols.json") as f:
    idols = json.load(f)

# =====================================================
# DB
# =====================================================
conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor()

# =====================================================
# 1️⃣ COMMUNITY
# =====================================================
community_rows = []
community_id_map = {}
community_counts = defaultdict(lambda: {"idols": 0, "members": 0})

for c in communities:
    cid = str(uuid.uuid4())
    t = random_datetime_recency(0.03)
    community_id_map[c["id"]] = cid

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

# =====================================================
# 2️⃣ USERS (IDOL)
# =====================================================
idol_user_ids = []
user_rows = []
seen_usernames = {}

for idol in idols:
    base = idol["stageName"].lower().replace(" ", "_")
    count = seen_usernames.get(base, 0)
    username = f"{base}_{count}" if count else base
    seen_usernames[base] = count + 1

    uid = str(uuid.uuid4())
    t = random_datetime_recency(0.05)
    cid = community_id_map[idol["communityId"]]

    user_rows.append((
        uid,
        f"{username}@idol.com",
        username,
        "$2b$10$KlvuCqbRNdRfVZZ.7TRIv.Jc/j9fG.vjedfKlQ.8aJWgoFAEpYIaW",
        "IDOL",
        AVATAR.format(random.randint(1, 70)),
        BG.format(random.randint(1, 1000)),
        cid,
        t, t
    ))

    idol_user_ids.append(uid)
    community_counts[cid]["idols"] += 1

# =====================================================
# 3️⃣ USERS (FAN)
# =====================================================
fan_user_ids = []

for i in range(TOTAL_FANS):
    uid = str(uuid.uuid4())
    t = random_datetime_recency(0.02)

    user_rows.append((
        uid,
        f"fan_{i}@mail.com",
        f"fan_{i}",
        "$2b$10$KlvuCqbRNdRfVZZ.7TRIv.Jc/j9fG.vjedfKlQ.8aJWgoFAEpYIaW",
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
""", user_rows)

idol_set = set(idol_user_ids)

# =====================================================
# 4️⃣ COMMUNITY FOLLOWER
# =====================================================
user_followed_communities = defaultdict(list)
follower_rows = []

for uid in fan_user_ids:
    for cid in community_id_map.values():
        if random.random() < FOLLOW_RATE:
            t = random_datetime_recency(0.08)
            follower_rows.append((
                str(uuid.uuid4()), True, t, t,
                0, False, None, Json({}), uid, cid
            ))
            user_followed_communities[uid].append(cid)
            community_counts[cid]["members"] += 1

execute_batch(cur, """
INSERT INTO community_follower (
  id, "isActive", "createdAt", "updatedAt",
  version, is_deleted, deleted_at,
  metadata, "userId", "communityId"
)
VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
""", follower_rows)

# =====================================================
# 5️⃣ POST
# =====================================================
post_rows = []

for uid in idol_user_ids + fan_user_ids:
    followed = user_followed_communities.get(uid)
    if not followed:
        continue

    lambda_val = RECENCY_LAMBDA_IDOL if uid in idol_set else RECENCY_LAMBDA_FAN

    for _ in range(random.randint(*post_range(uid, idol_set))):
        t = random_datetime_recency(lambda_val)

        cid = random.choice(followed)
        tags = sample_tags()
        content = generate_post_content(tags)

        media_urls = []
        if random.random() < POST_IMAGE_RATE:
            media_urls = [
                POST_IMAGE.format(random.randint(1, 10000))
                for _ in range(random.randint(1, 3))
            ]

        post_rows.append((
            str(uuid.uuid4()),
            content,
            Json({"tags": tags}),
            Json(media_urls),
            uid,
            cid,
            t, t
        ))

execute_batch(cur, """
INSERT INTO post (
  id, content, metadata, "media_urls",
  "authorId", "communityId",
  "createdAt", "updatedAt"
)
VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
""", post_rows)

# =====================================================
# 6️⃣ INTERACTION
# =====================================================
view_rows, like_rows, comment_rows = [], [], []
post_counts = defaultdict(lambda: {"views": 0, "likes": 0, "comments": 0})

for post_id, _, _, _, author_id, community_id, post_time, _ in post_rows:
    author_is_idol = author_id in idol_set

    viewers = random.sample(
        fan_user_ids,
        random.randint(*VIEW_RANGE)
    )

    for uid in viewers:
        if community_id not in user_followed_communities.get(uid, []) and \
           random.random() > NOISE_INTERACTION_RATE:
            continue

        t = interaction_datetime(post_time)

        view_rows.append((str(uuid.uuid4()), post_id, uid, t, t))
        post_counts[post_id]["views"] += 1

        like_prob = random.uniform(*LIKE_RATIO)
        comment_prob = random.uniform(*COMMENT_RATIO)

        if author_is_idol:
            like_prob *= IDOL_LIKE_BOOST
            comment_prob *= IDOL_COMMENT_BOOST

        if random.random() < min(like_prob, 1):
            like_rows.append((str(uuid.uuid4()), post_id, uid, t, t))
            post_counts[post_id]["likes"] += 1

        if random.random() < min(comment_prob, 1):
            comment_rows.append((
                str(uuid.uuid4()), "Nice post!",
                post_id, uid, t, t
            ))
            post_counts[post_id]["comments"] += 1

# =====================================================
# INSERT INTERACTION
# =====================================================
execute_batch(cur, """
INSERT INTO post_view (id,"postId","userId","createdAt","updatedAt")
VALUES (%s,%s,%s,%s,%s)
""", view_rows, page_size=1000)

execute_batch(cur, """
INSERT INTO post_like (id,"postId","userId","createdAt","updatedAt")
VALUES (%s,%s,%s,%s,%s)
""", like_rows, page_size=1000)

execute_batch(cur, """
INSERT INTO comment (id,content,"postId","userId","createdAt","updatedAt")
VALUES (%s,%s,%s,%s,%s,%s)
""", comment_rows, page_size=1000)

# =====================================================
# UPDATE COUNTS
# =====================================================
execute_batch(cur, """
UPDATE post
SET view_count=%s, like_count=%s, comment_count=%s
WHERE id=%s
""", [
    (
        post_counts[p[0]]["views"],
        post_counts[p[0]]["likes"],
        post_counts[p[0]]["comments"],
        p[0]
    ) for p in post_rows
])

execute_batch(cur, """
UPDATE community
SET total_idol=%s, total_member=%s
WHERE id=%s
""", [
    (community_counts[c[0]]["idols"], community_counts[c[0]]["members"], c[0])
    for c in community_rows
])

conn.commit()
cur.close()
conn.close()

print("🎉 SEED COMPLETED — LAST 6 MONTHS WITH STRONG RECENCY BIAS")
