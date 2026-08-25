from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from app.schemas.user import UserCreate, UserRead, UserUpdate
from app.models.user import User
from app.api.dependencies import get_db, get_current_user
from app.core.security import hash_password

router = APIRouter()

@router.post("/", response_model=UserRead)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    username_exists = db.query(User).filter(User.username == user.username).first()
    if username_exists:
        raise HTTPException(status_code=409, detail="Username already in use")
    email_exists = db.query(User).filter(User.email == user.email).first()
    if email_exists:
        raise HTTPException(status_code=409, detail="Email already in use")

    hashed_pw = hash_password(user.password)

    new_user = User(
        username=user.username,
        email=user.email,
        hashed_password=hashed_pw,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@router.get("/{user_id}", response_model=UserRead)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if current_user.id != user_id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not allowed")

    return user

@router.put("/{user_id}", response_model=UserRead)
def update_user(user_id: int, user_update: UserUpdate,
                db: Session = Depends(get_db),
                current_user: User = Depends(get_current_user)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if current_user.id != user_id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not allowed")

    if user_update.username:
        user.username = user_update.username

    if user_update.email:
        user.email = user_update.email

    db.commit()
    db.refresh(user)
    return user

@router.delete("/{user_id}")
def delete_user(user_id: int,
                db: Session = Depends(get_db),
                current_user: User = Depends(get_current_user)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if current_user.id != user_id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not allowed")

    db.delete(user)
    db.commit()
    return {"detail": "User deleted"}
