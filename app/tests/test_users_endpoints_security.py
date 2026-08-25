from sqlalchemy import text

def test_username_used(client, regular_user):
    response = client.post("/users/",
                   json={
                       "username": regular_user["username"],
                       "email": "dif@email",
                       "password": "testing"
                   },
    )
    assert response.status_code == 409

def test_email_used(client, regular_user):
    response = client.post("/users/",
        json={
            "username": "totally_different",
            "email": regular_user["email"],
            "password": "testing"
        },
    )
    assert response.status_code == 409