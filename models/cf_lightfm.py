from lightfm import LightFM

def train_cf(interactions, weights, no_components=30, loss='warp', epochs=30, num_threads=4):
    """
    Train collaborative filtering LightFM model
    """
    model = LightFM(no_components=no_components, loss=loss)
    model.fit(interactions, sample_weight=weights, epochs=epochs, num_threads=num_threads)
    return model
