from autonomous_betting_agent.restart_regression_package import package_fingerprint


def test_nested_volatile_keys_do_not_change_restart_fingerprint_extra_14():
    a = {"stable": 1, "nested": {"restart_regression_id": "a"}}
    b = {"stable": 1, "nested": {"restart_regression_id": "b"}}
    assert package_fingerprint(a) == package_fingerprint(b)
