import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.main import app
from app.database import SessionLocal
from app.core.security import hash_password

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()

@pytest.fixture
def regular_user(db):
    """A non-admin user. Deleted after the test."""
    db.execute(text("""
            INSERT INTO users (username, email, is_admin, hashed_password)
            VALUES (:u, :e, false, :p)
            ON CONFLICT (username) DO NOTHING
        """), {
        "u": "test_regular",
        "e": "regular@test.local",
        "p": hash_password("testpass123"),
    })
    db.commit()

    yield {"username": "test_regular", "password": "testpass123"}

    db.execute(text("DELETE FROM refresh_tokens WHERE user_id IN (SELECT id FROM users WHERE username = :u)"),
               {"u": "test_regular"})
    db.execute(text("DELETE FROM users WHERE username = 'test_regular'"))
    db.commit()


@pytest.fixture
def admin_user(db):
    """An admin user. Deleted after the test."""
    db.execute(text("""
            INSERT INTO users (username, email, is_admin, hashed_password)
            VALUES (:u, :e, true, :p)
            ON CONFLICT (username) DO NOTHING
        """), {
        "u": "test_admin",
        "e": "admin@test.local",
        "p": hash_password("testpass123"),
    })
    db.commit()

    yield {"username": "test_admin", "password": "testpass123"}

    db.execute(text("DELETE FROM refresh_tokens WHERE user_id IN (SELECT id FROM users WHERE username = :u)"),
               {"u": "test_admin"})
    db.execute(text("DELETE FROM users WHERE username = 'test_admin'"))
    db.commit()

@pytest.fixture
def regular_token(client, regular_user):
    response = client.post(
        "/auth/login",
        data = {
            "username": regular_user["username"],
            "password": regular_user["password"],
        },
    )

    assert response.status_code == 200, response.text
    return response.json()["access_token"]

@pytest.fixture
def admin_token(client, admin_user):
    response = client.post(
        "/auth/login",
        data = {
            "username": admin_user["username"],
            "password": admin_user["password"],
        },
    )

    assert response.status_code == 200, response.text
    return response.json()["access_token"]




