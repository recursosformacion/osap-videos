from starlette.requests import Request

from app import auth_session, safe_next


def test_safe_next_accepts_local_paths():
    assert safe_next("/works/123?resource=4") == "/works/123?resource=4"


def test_safe_next_rejects_external_and_ambiguous_paths():
    assert safe_next("https://attacker.example/") == "/"
    assert safe_next("//attacker.example/") == "/"
    assert safe_next(r"/\\attacker.example/") == "/"
    assert safe_next("/path\\\\attacker") == "/"
    assert safe_next("/path\r\nLocation: https://attacker.example") == "/"


def test_legacy_session_endpoint_rejects_foreign_origin():
    request = Request({
        "type": "http",
        "method": "POST",
        "path": "/auth/session",
        "headers": [(b"origin", b"https://attacker.example")],
    })

    response = auth_session(request, access_token="attacker-token")

    assert response.status_code == 403
