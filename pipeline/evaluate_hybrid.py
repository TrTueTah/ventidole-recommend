import numpy as np
from lightfm.evaluation import precision_at_k, recall_at_k, auc_score

from storage.save_load import load_model
from data.load_data import (
    load_users,
    load_posts,
    load_interactions,
    load_community_followers,
)
from data.preprocess import build_dataset

K = 10
NUM_THREADS = 4


def run():
    print("📥 Loading model...")
    model = load_model("hybrid_model.pkl")

    print("📥 Loading data from DB...")
    users_df = load_users()
    posts_df = load_posts()
    interactions_df = load_interactions()
    community_followers_df = load_community_followers()

    print("🛠 Rebuilding dataset & features...")
    dataset, interactions, weights, user_features, item_features = build_dataset(
        users_df,
        posts_df,
        interactions_df,
        community_followers_df,
    )

    print("📊 Evaluating model...")

    prec = precision_at_k(
        model,
        interactions,
        k=K,
        user_features=user_features,
        item_features=item_features,
        num_threads=NUM_THREADS,
    ).mean()

    rec = recall_at_k(
        model,
        interactions,
        k=K,
        user_features=user_features,
        item_features=item_features,
        num_threads=NUM_THREADS,
    ).mean()

    auc = auc_score(
        model,
        interactions,
        user_features=user_features,
        item_features=item_features,
        num_threads=NUM_THREADS,
    ).mean()

    print("===================================")
    print(f"🎯 Precision@{K}: {prec:.4f}")
    print(f"🎯 Recall@{K}:    {rec:.4f}")
    print(f"🎯 AUC:           {auc:.4f}")
    print("===================================")

    return {
        "precision@k": prec,
        "recall@k": rec,
        "auc": auc,
    }


if __name__ == "__main__":
    run()
