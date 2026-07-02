from autonomous_betting_agent.restart_regression_package import package_fingerprint


def test_nested_local_hashes_do_not_change_restart_fingerprint_extra_2():
    a = {"x": [{"generated_at_utc": "a", "local_review_hash": "1", "stable": 2}]}
    b = {"x": [{"generated_at_utc": "b", "local_review_hash": "2", "stable": 2}]}
    assert package_fingerprint(a) == package_fingerprint(b)
