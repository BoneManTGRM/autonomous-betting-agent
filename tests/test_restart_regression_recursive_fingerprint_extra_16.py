from autonomous_betting_agent.restart_regression_package import package_fingerprint


def test_nested_volatile_keys_do_not_change_restart_fingerprint_extra_16():
    a = {"stable": 1, "nested": {"dashboard_refresh_id": "a", "local_review_id": "b"}}
    b = {"stable": 1, "nested": {"dashboard_refresh_id": "c", "local_review_id": "d"}}
    assert package_fingerprint(a) == package_fingerprint(b)
