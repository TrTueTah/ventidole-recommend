from data.load_data import load_users, load_posts, load_interactions, load_community_followers
from data.preprocess import build_dataset
from models.hybrid_lightfm import train_hybrid
from storage.save_load import save_model

def run():
    print("📥 Loading data...")
    users_df = load_users()
    posts_df = load_posts()
    interactions_df = load_interactions()
    community_followers_df = load_community_followers()

    print("🛠 Building dataset...")
    dataset, interactions, weights, user_feat_matrix, item_feat_matrix = build_dataset(
        users_df, posts_df, interactions_df, community_followers_df
    )

    print("🚀 Training hybrid model...")
    model = train_hybrid(interactions, weights, user_feat_matrix, item_feat_matrix, epochs=30)

    print("💾 Saving model, dataset, and feature matrices...")
    save_model(model, "hybrid_model.pkl", dataset=dataset, 
              user_features=user_feat_matrix, item_features=item_feat_matrix)
    print("✅ Training complete.")

if __name__ == "__main__":
    run()
