from autonomous_betting_agent.restart_regression_package import package_fingerprint


def test_nested_dashboard_ids_do_not_change_restart_fingerprint_extra_4():
    a = {"stable": 1, "nested": {"dashboard_refresh_id": "a", "dashboard_refresh_hash": "b"}}
    b = {"stable": 1, "nested": {"dashboard_refresh_id": "c", "dashboard_refresh_hash": "d"}}
    assert package_fingerprint(a) == package_fingerprint(b)
