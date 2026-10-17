"""
tests/expected_anomalies.py
Ground-truth labels for the sample dataset injected anomalies.
Used to evaluate detector recall — NOT included in the uploaded dataset.
"""

EXPECTED_ANOMALIES = [
    {
        "metric": "revenue_usd",
        "approximate_period": "2023-08",  # month index 19
        "type": "sudden_drop",
        "expected_pct_change_below": -50.0,
        "expected_severity": ["High", "Critical"],
    },
    {
        "metric": "revenue_usd",
        "approximate_period": "2024-07",  # month index 30 (approx)
        "type": "spike",
        "expected_pct_change_above": 50.0,
        "expected_severity": ["High", "Critical"],
    },
    {
        "metric": "website_visitors",
        "approximate_period": "2024-01",  # month index 24
        "type": "spike",
        "expected_pct_change_above": 150.0,
        "expected_severity": ["High", "Critical"],
    },
    {
        "metric": "inventory_units",
        "approximate_period": "2023-08",
        "type": "sudden_drop",
        "note": "Near-stockout condition",
        "expected_severity": ["High", "Critical"],
    },
    {
        "metric": "expenses_usd",
        "approximate_period": "2024-01 onwards",
        "type": "trend_deterioration",
        "note": "Gradual expense inflation above baseline",
        "expected_severity": ["Low", "Medium"],
    },
]
