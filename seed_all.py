import psycopg2
import json
import uuid
import random
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

START_DATE = datetime(2023, 1, 1)
END_DATE = datetime(2025, 1, 1)

VIEW_RANGE = (5, 25)
LIKE_RATIO = (0.1, 0.3)
COMMENT_RATIO = (0.05, 0.15)

IDOL_LIKE_BOOST = 1.5
IDOL_COMMENT_BOOST = 2.0

AVATAR = "https://i.pravatar.cc/300?img={}"
BG = "https://picsum.photos/1200/400?random={}"
POST_IMAGE = "https://picsum.photos/800/600?random={}"

POST_IMAGE_RATE = 0.8  # 80% of posts have images

# =====================================================
# TAG SYSTEM (USER FRIENDLY)
# =====================================================
TAG_CATALOG = {
    "content": [
        "discussion",
        "fan_content",
        "announcement",
        "media"
    ],
    "theme": [
        "music",
        "kpop",
        "dance",
        "vocal",
        "choreography",
        "behind_the_scene",
        "daily_life",
        "collab"
    ],
    "mood": [
        "hype",
        "emotional",
        "funny",
        "wholesome",
        "serious"
    ],
    "event": [
        "concert",
        "fan_meet",
        "release",
        "practice"
    ]
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

MICRO_NOISE = [
    "",
    " ✨",
    " 💙",
    " 🎶",
    " today",
    " lately",
    " lately 😊"
]

# =====================================================
# UTILS
# =====================================================
def random_datetime():
    delta = END_DATE - START_DATE
    return START_DATE + timedelta(
        seconds=random.randint(0, int(delta.total_seconds()))
    )

def post_range(uid, idol_set):
    return POST_RANGE_IDOL if uid in idol_set else POST_RANGE_FAN

def sample_tags():
    tags = []

    tags.append(random.choice(TAG_CATALOG["content"]))

    tags.extend(random.sample(
        TAG_CATALOG["theme"],
        random.randint(1, 2)
    ))

    if random.random() < 0.4:
        tags.append(random.choice(TAG_CATALOG["mood"]))

    if random.random() < 0.2:
        tags.append(random.choice(TAG_CATALOG["event"]))

    return list(set(tags))

def generate_post_content(tags):
    primary = random.choice(tags)
    templates = POST_TEMPLATES.get(primary, [
        "Sharing something about {topic}"
    ])
    template = random.choice(templates)
    topic = primary.replace("_", " ")
    return template.format(topic=topic) + random.choice(MICRO_NOISE)

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
    t = random_datetime()
    community_id_map[c["id"]] = cid

    community_rows.append((
        cid,
        c["name"],
        c["communityType"],
        AVATAR.format(random.randint(1, 70)),
        BG.format(random.randint(1, 1000)),
        t,
        t
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
    stage = idol["stageName"].strip()
    base_username = stage.lower().replace(" ", "_").replace(".", "").replace(":", "")

    # Make username unique by adding a counter if duplicate
    if base_username in seen_usernames:
        seen_usernames[base_username] += 1
        username = f"{base_username}_{seen_usernames[base_username]}"
    else:
        seen_usernames[base_username] = 0
        username = base_username

    email = f"{username}@idol.com"

    uid = str(uuid.uuid4())
    t = random_datetime()
    cid = community_id_map[idol["communityId"]]

    user_rows.append((
        uid,
        email,
        username,
        "$2b$10$KlvuCqbRNdRfVZZ.7TRIv.Jc/j9fG.vjedfKlQ.8aJWgoFAEpYIaW",
        "IDOL",
        AVATAR.format(random.randint(1, 70)),
        BG.format(random.randint(1, 1000)),
        cid,
        t,
        t
    ))
    idol_user_ids.append(uid)
    community_counts[cid]["idols"] += 1

# =====================================================
# 3️⃣ USERS (FAN)
# =====================================================
fan_user_ids = []

for i in range(TOTAL_FANS):
    uid = str(uuid.uuid4())
    t = random_datetime()
    username = f"fan_{i}"
    email = f"{username}@mail.com"

    user_rows.append((
        uid,
        email,
        username,
        "$2b$10$KlvuCqbRNdRfVZZ.7TRIv.Jc/j9fG.vjedfKlQ.8aJWgoFAEpYIaW",
        "FAN",
        AVATAR.format(random.randint(1, 70)),
        None,
        None,
        t,
        t
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
            t = random_datetime()
            follower_rows.append((
                str(uuid.uuid4()),
                True,
                t,
                t,
                0,
                False,
                None,
                Json({}),
                uid,
                cid
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

    for _ in range(random.randint(*post_range(uid, idol_set))):
        t = random_datetime()

        cid = (
            random.choice(followed)
            if random.random() > NOISE_POST_RATE
            else random.choice(list(community_id_map.values()))
        )

        tags = sample_tags()
        content = generate_post_content(tags)

        # Generate media URLs for 80% of posts
        media_urls = []
        if random.random() < POST_IMAGE_RATE:
            num_images = random.randint(1, 3)
            media_urls = [
                POST_IMAGE.format(random.randint(1, 10000))
                for _ in range(num_images)
            ]

        post_rows.append((
            str(uuid.uuid4()),
            content,
            Json({"tags": tags}),
            Json(media_urls),
            uid,
            cid,
            t,
            t
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
        follows = community_id in user_followed_communities.get(uid, [])
        if not follows and random.random() > NOISE_INTERACTION_RATE:
            continue

        t = post_time + timedelta(
            minutes=random.randint(1, 60 * 24 * 14)
        )

        view_rows.append((
            str(uuid.uuid4()),
            post_id,
            uid,
            t,
            t
        ))
        post_counts[post_id]["views"] += 1

        like_prob = random.uniform(*LIKE_RATIO)
        comment_prob = random.uniform(*COMMENT_RATIO)

        if author_is_idol:
            like_prob *= IDOL_LIKE_BOOST
            comment_prob *= IDOL_COMMENT_BOOST

        if random.random() < min(like_prob, 1):
            like_rows.append((
                str(uuid.uuid4()),
                post_id,
                uid,
                t,
                t
            ))
            post_counts[post_id]["likes"] += 1

        if random.random() < min(comment_prob, 1):
            comment_rows.append((
                str(uuid.uuid4()),
                f"Nice post!",
                post_id,
                uid,
                t,
                t
            ))
            post_counts[post_id]["comments"] += 1

# =====================================================
# INSERT INTERACTION
# =====================================================
execute_batch(cur, """
INSERT INTO post_view (
  id, "postId", "userId",
  "createdAt", "updatedAt"
)
VALUES (%s,%s,%s,%s,%s)
""", view_rows, page_size=1000)

execute_batch(cur, """
INSERT INTO post_like (
  id, "postId", "userId",
  "createdAt", "updatedAt"
)
VALUES (%s,%s,%s,%s,%s)
""", like_rows, page_size=1000)

execute_batch(cur, """
INSERT INTO comment (
  id, content,
  "postId", "userId",
  "createdAt", "updatedAt"
)
VALUES (%s,%s,%s,%s,%s,%s)
""", comment_rows, page_size=1000)

# =====================================================
# UPDATE POST COUNTS
# =====================================================
update_rows = [
    (
        post_counts[post_id]["views"],
        post_counts[post_id]["likes"],
        post_counts[post_id]["comments"],
        post_id
    )
    for post_id, _, _, _, _, _, _, _ in post_rows
]

execute_batch(cur, """
UPDATE post
SET view_count = %s,
    like_count = %s,
    comment_count = %s
WHERE id = %s
""", update_rows, page_size=1000)

# =====================================================
# UPDATE COMMUNITY COUNTS
# =====================================================
community_update_rows = [
    (
        community_counts[cid]["idols"],
        community_counts[cid]["members"],
        cid
    )
    for cid, _, _, _, _, _, _ in community_rows
]

execute_batch(cur, """
UPDATE community
SET total_idol = %s,
    total_member = %s
WHERE id = %s
""", community_update_rows)

conn.commit()
cur.close()
conn.close()

print("🎉 SEED COMPLETED — USER FRIENDLY TAG VERSION")
