from sqlalchemy import text

def test_register_creates_user(client, db):
    try:
        response = client.post("/users/",
               json = {
                    "username": "test_newuser",
                    "email": "newuser@email",
                    "password": "test_password"
               },
        )
        assert response.status_code == 200

        # Test response_model
        body = response.json()
        assert body["username"] == "test_newuser"
        assert "hashed_password" not in body
        assert "password" not in body
    finally:
        # cleanup
        db.execute(text("DELETE FROM users WHERE username = 'test_newuser'"))
        db.commit()

def test_wrong_data_input(client):
    response = client.post("/users/",
               json={
                   "username": "test_newuser",
                   "email": "newuser@email",
                   "password": None
               },
    )
    assert response.status_code == 422


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