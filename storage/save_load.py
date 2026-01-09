import pickle

def save_model(model, path, dataset=None):
    """
    Save model and optionally the dataset.
    If dataset is provided, saves both in a dictionary to preserve feature mappings.
    """
    with open(path, "wb") as f:
        if dataset is not None:
            pickle.dump({'model': model, 'dataset': dataset}, f)
        else:
            pickle.dump(model, f)

def load_model(path):
    """
    Load model (and dataset if it was saved together).
    Returns tuple (model, dataset) or just model for backward compatibility.
    """
    with open(path, "rb") as f:
        data = pickle.load(f)
        if isinstance(data, dict) and 'model' in data:
            return data['model'], data.get('dataset')
        else:
            return data, None
