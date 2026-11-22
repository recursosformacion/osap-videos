from app import safe_next


def test_safe_next_accepts_local_paths():
    assert safe_next("/works/123?resource=4") == "/works/123?resource=4"


def test_safe_next_rejects_external_and_ambiguous_paths():
    assert safe_next("https://attacker.example/") == "/"
    assert safe_next("//attacker.example/") == "/"
    assert safe_next(r"/\\attacker.example/") == "/"
    assert safe_next("/path\\\\attacker") == "/"
    assert safe_next("/path\r\nLocation: https://attacker.example") == "/"
