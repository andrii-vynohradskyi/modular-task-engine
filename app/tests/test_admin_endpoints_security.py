from app.tests.conftest import regular_token


def test_admin_endpoint_requires_auth(client):
    response = client.get("/admin/queue")
    assert response.status_code == 401

def test_admin_endpoint_rejects_non_admin(client, regular_token):
    response = client.get(
        "/admin/queue",
        headers={"Authorization": f"Bearer {regular_token}"},
    )
    assert response.status_code == 403

def test_admin_endpoint_allows_admin(client, admin_token):
    response = client.get(
        "/admin/queue",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200