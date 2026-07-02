from autonomous_betting_agent.restart_regression_package import package_fingerprint


def test_nested_restart_ids_do_not_change_restart_fingerprint_extra_3():
    a = {"stable": 1, "nested": {"restart_regression_id": "a", "restart_regression_hash": "b"}}
    b = {"stable": 1, "nested": {"restart_regression_id": "c", "restart_regression_hash": "d"}}
    assert package_fingerprint(a) == package_fingerprint(b)
