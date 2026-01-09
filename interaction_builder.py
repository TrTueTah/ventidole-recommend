from lightfm.data import Dataset

INTERACTION_WEIGHT = {
    "view": 1.0,
    "like": 3.0,
    "comment": 5.0
}

def build_dataset(users, posts, interactions):
    dataset = Dataset()

    dataset.fit(
        users=users["id"].tolist(),
        items=posts["id"].tolist()
    )

    interaction_tuples = [
        (row.userId, row.postId, INTERACTION_WEIGHT[row.type])
        for row in interactions.itertuples()
    ]

    interactions_matrix, weights = dataset.build_interactions(
        interaction_tuples
    )

    return dataset, interactions_matrix, weights
