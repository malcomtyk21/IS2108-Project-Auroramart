import os
import pandas as pd
import joblib

_MODEL_PATH = os.path.join(os.path.dirname(__file__), "mlmodels", "b2c_customers_100.joblib")
try:
    loaded_model = joblib.load(_MODEL_PATH)
except Exception:
    loaded_model = None

# Association rules model for product recommendations (notebook style)
_RULES_PATH = os.path.join(os.path.dirname(__file__), "mlmodels", "b2c_products_500_transactions_50k.joblib")
try:
    loaded_rules = joblib.load(_RULES_PATH)
except Exception:
    loaded_rules = None


def _predict_with_dict(model, customer_data):
    columns = {
        'age': 'int64', 'household_size': 'int64', 'has_children': 'int64', 'monthly_income_sgd': 'float64',
        'gender_Female': 'bool', 'gender_Male': 'bool', 'employment_status_Full-time': 'bool',
        'employment_status_Part-time': 'bool', 'employment_status_Retired': 'bool',
        'employment_status_Self-employed': 'bool', 'employment_status_Student': 'bool',
        'occupation_Admin': 'bool', 'occupation_Education': 'bool', 'occupation_Sales': 'bool',
        'occupation_Service': 'bool', 'occupation_Skilled Trades': 'bool', 'occupation_Tech': 'bool',
        'education_Bachelor': 'bool', 'education_Diploma': 'bool', 'education_Doctorate': 'bool',
        'education_Master': 'bool', 'education_Secondary': 'bool'
    }

    df = pd.DataFrame({col: pd.Series(dtype=dtype) for col, dtype in columns.items()})
    customer_df = pd.DataFrame([customer_data])
    customer_encoded = pd.get_dummies(customer_df, columns=['gender', 'employment_status', 'occupation', 'education'])

    for col in df.columns:
        if col not in customer_encoded.columns:
            # Use False for bool columns, 0 for numeric
            if df[col].dtype == bool:
                df[col] = False
            else:
                df[col] = 0
        else:
            df[col] = customer_encoded[col]

    return model.predict(df)


def get_recommendations(rules, items, metric='confidence', top_n=5):
    """Return up to `top_n` recommended item ids using the provided rules DataFrame.

    This follows the notebook implementation: filter rules where the given
    item is in the antecedents, sort by `metric`, and collect consequents.
    If `rules` is None, return an empty list.
    """
    if rules is None:
        return []

    recommendations = set()
    for item in items:
        # rules DataFrame stores antecedents as iterable-like values
        matched = rules[rules['antecedents'].apply(lambda x: item in x)]
        top_rules = matched.sort_values(by=metric, ascending=False).head(top_n)
        for _, row in top_rules.iterrows():
            # consequents may be a frozenset/list; add all members
            try:
                recommendations.update(row['consequents'])
            except Exception:
                continue

    recommendations.difference_update(items)
    return list(recommendations)[:top_n]


def predict_preferred_category(profile):
    if profile is None:
        return ""

    # Convert profile (Django model) to a lightweight dict.
    customer_data = {
        'age': getattr(profile, 'age', None),
        'household_size': getattr(profile, 'household_size', None),
        'has_children': 1 if getattr(profile, 'has_children', False) else 0,
        'monthly_income_sgd': getattr(profile, 'monthly_income_sgd', None),
        'gender': getattr(profile, 'gender', None),
        'employment_status': getattr(profile, 'employment_status', None),
        'occupation': getattr(profile, 'occupation', None),
        'education': getattr(profile, 'education', None),
    }

    model = loaded_model
    if model is None:
        # No model at import time; avoid raising in production code — return empty.
        return ""

    try:
        pred = _predict_with_dict(model, customer_data)
        return str(pred[0])
    except Exception:
        return ""
