"""Accounts: sign up, log in, and the logged-in user's home location."""
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.config import JWT_EXPIRE_MINUTES, JWT_SECRET
from app.db import SessionLocal, User
from app.ml_client import location_names

router = APIRouter(prefix="/api")

JWT_ALGORITHM = "HS256"
hasher = PasswordHasher()
bearer = HTTPBearer(auto_error=False)

# Checked when an email has no account, so that login takes the same time either way and
# can't be used to find out who has an account
UNKNOWN_USER_HASH = hasher.hash("no account has this password")


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    home_location: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(max_length=128)


class HomeRequest(BaseModel):
    home_location: str | None


def normalise_email(email):
    return email.strip().lower()


def check_location(name):
    if name is not None and name not in location_names():
        raise HTTPException(status_code=422, detail=f"Unknown location: {name}")


def user_data(user):
    return {"id": user.id, "email": user.email, "home_location": user.home_location}


def login_response(user):
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {"sub": str(user.id), "iat": now, "exp": now + timedelta(minutes=JWT_EXPIRE_MINUTES)},
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )
    return {"access_token": token, "token_type": "bearer", "user": user_data(user)}


def not_logged_in():
    return HTTPException(status_code=401, detail="Not logged in.", headers={"WWW-Authenticate": "Bearer"})


def current_user_id(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    """The user ID from a valid login token. Rejects missing, altered and expired tokens."""
    if credentials is None:
        raise not_logged_in()
    try:
        payload = jwt.decode(
            credentials.credentials,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
            options={"require": ["exp", "sub"]},
        )
        return int(payload["sub"])
    except (jwt.InvalidTokenError, ValueError):
        raise not_logged_in()


@router.post("/auth/register", status_code=201)
def register(request: RegisterRequest):
    check_location(request.home_location)
    user = User(
        email=normalise_email(request.email),
        password_hash=hasher.hash(request.password),
        home_location=request.home_location,
    )
    try:
        with SessionLocal.begin() as session:
            session.add(user)
            session.flush()
            return login_response(user)
    except IntegrityError:
        raise HTTPException(status_code=409, detail="An account with this email already exists.")


@router.post("/auth/login")
def login(request: LoginRequest):
    with SessionLocal() as session:
        user = session.scalar(select(User).where(User.email == normalise_email(request.email)))
        try:
            hasher.verify(user.password_hash if user else UNKNOWN_USER_HASH, request.password)
        except (VerificationError, InvalidHashError):
            user = None
        if user is None:
            # The same message for both cases, so it doesn't reveal which emails have accounts
            raise HTTPException(status_code=401, detail="Incorrect email or password.")
        return login_response(user)


@router.get("/me")
def me(user_id: int = Depends(current_user_id)):
    with SessionLocal() as session:
        user = session.get(User, user_id)
        if user is None:
            raise not_logged_in()
        return user_data(user)


@router.patch("/me")
def update_home(request: HomeRequest, user_id: int = Depends(current_user_id)):
    check_location(request.home_location)
    with SessionLocal.begin() as session:
        user = session.get(User, user_id)
        if user is None:
            raise not_logged_in()
        user.home_location = request.home_location
        return user_data(user)
