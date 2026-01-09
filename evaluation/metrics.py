from lightfm.evaluation import precision_at_k, recall_at_k, auc_score

def evaluate_model(model, interactions, user_features, item_features, k=10):
    prec = precision_at_k(model, interactions, user_features=user_features, item_features=item_features, k=k).mean()
    rec = recall_at_k(model, interactions, user_features=user_features, item_features=item_features, k=k).mean()
    auc = auc_score(model, interactions, user_features=user_features, item_features=item_features).mean()
    return prec, rec, auc
