#!/usr/bin/env python3
"""
Quick script to retrain the model with proper feature matrix saving.
Run this to fix the feature mismatch issue.
"""
from data.load_data import load_users, load_posts, load_interactions, load_community_followers
from data.preprocess import build_dataset
from models.hybrid_lightfm import train_hybrid
from storage.save_load import save_model

print("=" * 80)
print("RETRAINING MODEL WITH FEATURE MATRICES")
print("=" * 80)

print("\n📥 Loading data from database...")
users_df = load_users()
posts_df = load_posts()
interactions_df = load_interactions()
community_followers_df = load_community_followers()
print(f"✅ Loaded {len(users_df)} users, {len(posts_df)} posts, {len(interactions_df)} interactions")

print("\n🛠 Building dataset and feature matrices...")
dataset, interactions, weights, user_feat_matrix, item_feat_matrix = build_dataset(
    users_df, posts_df, interactions_df, community_followers_df
)
print(f"✅ Dataset built: {user_feat_matrix.shape[0]} users, {item_feat_matrix.shape[0]} items")
print(f"   User features shape: {user_feat_matrix.shape}")
print(f"   Item features shape: {item_feat_matrix.shape}")

print("\n🚀 Training hybrid model (30 epochs)...")
model = train_hybrid(interactions, weights, user_feat_matrix, item_feat_matrix, epochs=30)
print("✅ Training complete")

print("\n💾 Saving model, dataset, and feature matrices...")
save_model(model, "hybrid_model.pkl", dataset=dataset, 
          user_features=user_feat_matrix, item_features=item_feat_matrix)
print("✅ Saved to hybrid_model.pkl")

print("\n" + "=" * 80)
print("SUCCESS! Model retrained with feature matrices included.")
print("The API should now work correctly without feature mismatch errors.")
print("=" * 80)
