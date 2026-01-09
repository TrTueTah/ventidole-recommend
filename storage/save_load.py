import pickle

def save_model(model, path, dataset=None, user_features=None, item_features=None):
    """
    Save model, dataset, and feature matrices.
    Saves all components needed for consistent inference.
    """
    with open(path, "wb") as f:
        if dataset is not None:
            pickle.dump({
                'model': model,
                'dataset': dataset,
                'user_features': user_features,
                'item_features': item_features
            }, f)
        else:
            pickle.dump(model, f)

def load_model(path):
    """
    Load model, dataset, and feature matrices.
    Returns tuple (model, dataset, user_features, item_features)
    or just model for backward compatibility.
    """
    with open(path, "rb") as f:
        data = pickle.load(f)
        if isinstance(data, dict) and 'model' in data:
            return (
                data['model'],
                data.get('dataset'),
                data.get('user_features'),
                data.get('item_features')
            )
        else:
            return data, None, None, None
