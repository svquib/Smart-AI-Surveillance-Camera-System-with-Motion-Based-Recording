"""Register / login / me.

There are two login routes on purpose:
  - POST /auth/login  takes JSON {email, password}  -> what the React app uses
  - POST /auth/token  takes a form  -> what Swagger's Authorize button needs
Both hand back the same JWT.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, Token, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=201)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        name=payload.name,
        email=payload.email,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _authenticate(db: Session, email: str, password: str) -> User:
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.hashed_password):
        # Same message for both cases so we don't leak which emails exist.
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    return user


@router.post("/login", response_model=Token)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = _authenticate(db, payload.email, payload.password)
    return Token(access_token=create_access_token(user.id))


@router.post("/token", response_model=Token, include_in_schema=False)
def login_form(
    form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
):
    # OAuth2 form uses "username"; we treat it as the email.
    user = _authenticate(db, form.username, form.password)
    return Token(access_token=create_access_token(user.id))


@router.get("/me", response_model=UserOut)
def me(current: User = Depends(get_current_user)):
    return current
