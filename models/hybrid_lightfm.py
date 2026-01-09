from .cf_lightfm import train_cf
from .content_based import train_content

def train_hybrid(interactions, weights, user_features, item_features, epochs=30):
    """
    Train a hybrid LightFM model: CF + Content-based
    """
    model = train_content(interactions, weights, user_features, item_features, epochs=epochs)
    return model
