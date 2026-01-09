from storage.save_load import load_model
from data.load_data import load_users, load_posts, load_interactions, load_community_followers
from data.preprocess import build_dataset
import numpy as np

TOP_K = 10

def run(user_id=None):
    print("📥 Loading model...")
    model = load_model("hybrid_model.pkl")

    print("📥 Loading data...")
    users_df = load_users()
    posts_df = load_posts()
    interactions_df = load_interactions()
    community_followers_df = load_community_followers()

    print("🛠 Building dataset...")
    dataset, interactions, weights, user_feat_matrix, item_feat_matrix = build_dataset(
        users_df, posts_df, interactions_df, community_followers_df
    )

    user_mapping = dataset.mapping()[0]
    item_mapping = dataset.mapping()[2]
    rev_item_mapping = {v: k for k, v in item_mapping.items()}

    # recommend for all users if not specified
    if user_id:
        user_ids = [user_id]
    else:
        user_ids = users_df['id'].tolist()

    recommendations = {}
    for uid in user_ids:
        if uid not in user_mapping:
            continue
        uidx = user_mapping[uid]
        scores = model.predict(uidx, np.arange(len(item_mapping)), item_features=item_feat_matrix)
        top_items = np.argsort(-scores)[:TOP_K]
        recommendations[uid] = [rev_item_mapping[i] for i in top_items]

    return recommendations

if __name__ == "__main__":
    recs = run()
    for uid, items in recs.items():
        print(f"User {uid}: Recommended posts: {items}")
