from autonomous_betting_agent.restart_regression_package import package_fingerprint


def test_nested_volatile_keys_do_not_change_restart_fingerprint_extra_7():
    a = {"stable": 1, "nested": {"generated_at_utc": "a", "dashboard_refresh_hash": "b"}}
    b = {"stable": 1, "nested": {"generated_at_utc": "c", "dashboard_refresh_hash": "d"}}
    assert package_fingerprint(a) == package_fingerprint(b)
