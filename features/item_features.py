def build_item_features(df_posts):
    """
    Return list of (item_id, features) tuples
    """
    item_features = []
    for _, row in df_posts.iterrows():
        feat = list(row['tags_flat'])
        if row.get('communityId'):
            feat.append(f"community:{row['communityId']}")
        item_features.append((row['id'], feat))
    return item_features
