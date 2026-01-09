from lightfm import LightFM

def train_content(interactions, weights, user_features, item_features, no_components=30, loss='warp', epochs=30, num_threads=4):
    """
    Train content-based LightFM model using user/item features
    """
    model = LightFM(no_components=no_components, loss=loss)
    model.fit(
        interactions,
        sample_weight=weights,
        user_features=user_features,
        item_features=item_features,
        epochs=epochs,
        num_threads=num_threads
    )
    return model
