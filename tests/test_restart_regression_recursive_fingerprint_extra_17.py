from autonomous_betting_agent.restart_regression_package import package_fingerprint


def test_nested_volatile_keys_do_not_change_restart_fingerprint_extra_17():
    a = {"stable": 1, "nested": {"dashboard_refresh_hash": "a", "local_review_hash": "b"}}
    b = {"stable": 1, "nested": {"dashboard_refresh_hash": "c", "local_review_hash": "d"}}
    assert package_fingerprint(a) == package_fingerprint(b)
