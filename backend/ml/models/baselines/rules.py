RULES = {
    "high_value_user": lambda r: (
        r.get("total_events", 0) > 100
        and r.get("days_active", 0) > 20
        and r.get("is_purchaser", 0) == 1
    ),
    "at_risk_user": lambda r: (
        r.get("hours_since_last_event", 0) > 168
        and r.get("total_events", 0) > 10
    ),
    "power_user": lambda r: (
        r.get("event_density", 0) > 5
        and r.get("session_count", 0) > 20
    ),
    "one_time_visitor": lambda r: (
        r.get("total_events", 0) <= 3
        and r.get("days_active", 0) <= 1
    ),
}


def apply_rules(features: pd.DataFrame) -> pd.DataFrame:
    results = []
    for _, row in features.iterrows():
        labels = [name for name, fn in RULES.items() if fn(row)]
        results.append(labels)
    return pd.Series(results, index=features.index)
