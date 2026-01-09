import pandas as pd
import numpy as np
from lightfm.data import Dataset
from sklearn.preprocessing import MultiLabelBinarizer

def build_user_item_features(users, posts, interactions, community_followers):
    # =====================
    # User features: role + communities follow
    # =====================
    user_roles = users.set_index('id')['role'].to_dict()
    all_communities = community_followers['communityId'].unique().tolist()

    user_features_dict = {}
    for uid in users['id']:
        features = [f"role:{user_roles[uid]}"]
        comms = community_followers.loc[community_followers['userId']==uid, 'communityId'].tolist()
        for c in comms:
            features.append(f"community:{c}")
        user_features_dict[uid] = features

    # =====================
    # Item features: tags + community
    # =====================
    item_features_dict = {}
    for _, row in posts.iterrows():
        meta = row['metadata'] if isinstance(row['metadata'], dict) else {}
        tags = meta.get('tags', [])
        comm = row['communityId']
        feats = [f"tag:{t}" for t in tags] + [f"community:{comm}"]
        item_features_dict[row['id']] = feats

    return user_features_dict, item_features_dict

def build_dataset(users, posts, interactions, community_followers):
    user_feats, item_feats = build_user_item_features(users, posts, interactions, community_followers)
    dataset = Dataset()

    dataset.fit(
        users=users['id'].tolist(),
        items=posts['id'].tolist(),
        user_features=np.unique([f for feats in user_feats.values() for f in feats]).tolist(),
        item_features=np.unique([f for feats in item_feats.values() for f in feats]).tolist()
    )

    # Build interactions matrix
    interactions_matrix, weights = dataset.build_interactions([
        (row['user_id'], row['post_id'], 1.0) for _, row in interactions.iterrows()
    ])

    # Build features matrices
    user_features_matrix = dataset.build_user_features([
        (uid, feats) for uid, feats in user_feats.items()
    ])
    item_features_matrix = dataset.build_item_features([
        (iid, feats) for iid, feats in item_feats.items()
    ])

    return dataset, interactions_matrix, weights, user_features_matrix, item_features_matrix
