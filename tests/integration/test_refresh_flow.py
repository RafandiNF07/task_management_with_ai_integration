import uuid
import pytest

pytestmark = pytest.mark.asyncio


async def test_login_refresh_revoke_flow(client):
    # Register
    uid = uuid.uuid4().hex[:8]
    username = f"r_{uid}"
    await client.post("/api/v1/auth/register", json={"username": username, "password": "p"})

    # Login (form-data)
    login_resp = await client.post(
        "/api/v1/auth/login",
        data={"username": username, "password": "p"},
    )
    assert login_resp.status_code == 200
    data = login_resp.json()
    assert "access_token" in data
    assert "refresh_token" in data

    access = data["access_token"]
    refresh = data["refresh_token"]

    # Access protected endpoint with access token
    me_resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access}"})
    assert me_resp.status_code == 200

    # Use refresh token to obtain new access token
    refresh_resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert refresh_resp.status_code == 200
    new_access = refresh_resp.json().get("access_token")
    assert new_access and new_access != access

    # Use new access token to access protected endpoint
    me2 = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {new_access}"})
    assert me2.status_code == 200

    # Revoke (logout) the refresh token
    revoke_resp = await client.post("/api/v1/auth/logout", json={"refresh_token": refresh})
    assert revoke_resp.status_code == 200
    assert revoke_resp.json().get("status") in {"revoked", "not_found_or_already_revoked"}

    # Attempt to refresh again with the same (revoked) refresh token -> should be unauthorized
    refresh_after = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert refresh_after.status_code == 401
