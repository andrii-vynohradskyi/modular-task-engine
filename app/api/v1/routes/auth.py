from fastapi import APIRouter, Depends, HTTPException, status, Response, Cookie
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone

from app.api.dependencies import get_db
from app.models.user import User
from app.models.refresh_token import RefreshToken
from app.core.security import verify_password, hash_token, verify_token_hash
from app.core.jwt import create_access_token, create_refresh_token, decode_token
from app.schemas.token import TokenPair
from app.core.config import settings

from fastapi.security import OAuth2PasswordRequestForm

router = APIRouter()

from app.api.dependencies import get_current_user
from app.schemas.user import UserRead

@router.get("/me", response_model=UserRead)
def me(current_user = Depends(get_current_user)):
    return current_user

@router.post("/login", response_model=TokenPair)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db), response: Response = None):
    # OAuth2PasswordRequestForm expects form fields: username, password
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    # create tokens
    access_token = create_access_token(subject=user.id)
    refresh_token = create_refresh_token(subject=user.id)
    # store hashed refresh in DB with expiry
    rt_hash = hash_token(refresh_token)
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    db_rt = RefreshToken(user_id=user.id, token_hash=rt_hash, expires_at=expires_at)
    db.add(db_rt)
    db.commit()
    # Set refresh token as HttpOnly cookie (recommended for browser clients)
    response.set_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=settings.REFRESH_COOKIE_SECURE,
        samesite=settings.REFRESH_COOKIE_SAMESITE,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/refresh", response_model=TokenPair)
def refresh(response: Response, refresh_token_cookie: str | None = Cookie(None), db: Session = Depends(get_db)):
    # Accept refresh token from cookie
    if not refresh_token_cookie:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing refresh token")
    try:
        payload = decode_token(refresh_token_cookie)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Wrong token type")
    user_id = int(payload.get("sub"))
    # find matching non-revoked token hash in DB
    tokens = db.query(RefreshToken).filter(RefreshToken.user_id == user_id, RefreshToken.revoked == False).all()
    matched = None
    for t in tokens:
        if verify_token_hash(refresh_token_cookie, t.token_hash):
            matched = t
            break
    if not matched:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token not found")
    # Issue new access token (and optionally new refresh)
    access_token = create_access_token(subject=user_id)
    # Optionally rotate refresh token: create new, store hashed, revoke old
    new_refresh = create_refresh_token(subject=user_id)
    matched.revoked = True
    db.add(matched)
    new_hash = hash_token(new_refresh)
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    db_new = RefreshToken(user_id=user_id, token_hash=new_hash, expires_at=expires_at)
    db.add(db_new)
    db.commit()
    # set new cookie
    response.set_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        value=new_refresh,
        httponly=True,
        secure=settings.REFRESH_COOKIE_SECURE,
        samesite=settings.REFRESH_COOKIE_SAMESITE,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/logout")
def logout(response: Response, refresh_token_cookie: str | None = Cookie(None), db: Session = Depends(get_db)):
    # Revoke refresh token in DB if present
    if refresh_token_cookie:
        try:
            payload = decode_token(refresh_token_cookie)
            user_id = int(payload.get("sub"))
            tokens = db.query(RefreshToken).filter(RefreshToken.user_id == user_id, RefreshToken.revoked == False).all()
            for t in tokens:
                if verify_token_hash(refresh_token_cookie, t.token_hash):
                    t.revoked = True
                    db.add(t)
                    db.commit()
                    break
        except Exception:
            pass
    # delete cookie client-side
    response.delete_cookie(settings.REFRESH_COOKIE_NAME)
    return {"msg": "Logged out"}
