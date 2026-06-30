from autonomous_betting_agent import sidebar_nav


def test_s52_subscriber_page_in_sidebar():
    target = "pages/" + "subscriber_intelligence" + ".py"
    assert target in {item[2] for item in sidebar_nav.TOOLS}


def test_s52_subscriber_language_key_present():
    target = "subscriber_intelligence" + "_language"
    assert target in set(sidebar_nav.LANGUAGE_KEYS)
