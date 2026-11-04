"""Accounts: sign up, log in, roles, and the logged-in user's own settings."""
import logging
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.config import ADMIN_EMAIL, ADMIN_PASSWORD, JWT_EXPIRE_MINUTES, JWT_SECRET
from app.db import SessionLocal, User
from app.ml_client import location_names
from app.realtime import clear_failed_logins, record_failed_login, too_many_failed_logins

log = logging.getLogger("uvicorn.error")
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


class PasswordRequest(BaseModel):
    current_password: str = Field(max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


def password_matches(password_hash, password):
    try:
        return hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def seed_admin():
    """Create the admin account from .env, or bring it into line if .env has changed."""
    if not ADMIN_EMAIL or not ADMIN_PASSWORD:
        log.warning("ADMIN_EMAIL or ADMIN_PASSWORD is not set, so there is no admin account.")
        return
    with SessionLocal.begin() as session:
        admin = session.scalar(select(User).where(User.email == ADMIN_EMAIL))
        if admin is None:
            session.add(User(email=ADMIN_EMAIL, password_hash=hasher.hash(ADMIN_PASSWORD), is_admin=True))
            return
        admin.is_admin = True
        admin.is_active = True
        if not password_matches(admin.password_hash, ADMIN_PASSWORD):
            admin.password_hash = hasher.hash(ADMIN_PASSWORD)


def normalise_email(email):
    return email.strip().lower()


def check_location(name):
    if name is not None and name not in location_names():
        raise HTTPException(status_code=422, detail=f"Unknown location: {name}")


def user_data(user):
    return {"id": user.id, "email": user.email, "home_location": user.home_location, "is_admin": user.is_admin}


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


def decode_token(token):
    """The user ID and expiry time from a valid token. Raises ValueError for anything else."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM], options={"require": ["exp", "sub"]})
        return int(payload["sub"]), payload["exp"]
    except jwt.InvalidTokenError as e:
        raise ValueError(str(e))


def active_user(user_id):
    """The user, if they still exist and are not disabled. Roles are read from the database on
    every request, so disabling someone takes effect at once, even with an unexpired token."""
    with SessionLocal() as session:
        user = session.get(User, user_id)
        return user if user and user.is_active else None


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    if credentials is None:
        raise not_logged_in()
    try:
        user_id, _ = decode_token(credentials.credentials)
    except ValueError:
        raise not_logged_in()
    user = active_user(user_id)
    if user is None:
        raise not_logged_in()
    return user


def current_admin(user: User = Depends(current_user)):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admins only.")
    return user


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
def login(body: LoginRequest, request: Request):
    email = normalise_email(body.email)
    # nginx sets X-Real-IP. Limiting by email and address together means an attacker elsewhere
    # can't lock someone out of their own account.
    limit_key = f"{email}:{request.headers.get('x-real-ip') or request.client.host}"
    if too_many_failed_logins(limit_key):
        raise HTTPException(status_code=429, detail="Too many failed attempts. Try again in 15 minutes.")

    with SessionLocal() as session:
        user = session.scalar(select(User).where(User.email == email))
    if not password_matches(user.password_hash if user else UNKNOWN_USER_HASH, body.password) or user is None:
        record_failed_login(limit_key)
        # The same message for both cases, so it doesn't reveal which emails have accounts
        raise HTTPException(status_code=401, detail="Incorrect email or password.")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="This account has been disabled.")
    clear_failed_logins(limit_key)
    return login_response(user)


@router.get("/me")
def me(user: User = Depends(current_user)):
    return user_data(user)


@router.patch("/me")
def update_home(request: HomeRequest, user: User = Depends(current_user)):
    check_location(request.home_location)
    with SessionLocal.begin() as session:
        stored = session.get(User, user.id)
        stored.home_location = request.home_location
        return user_data(stored)


@router.post("/me/password", status_code=204)
def change_password(request: PasswordRequest, user: User = Depends(current_user)):
    if not password_matches(user.password_hash, request.current_password):
        raise HTTPException(status_code=403, detail="Your current password is incorrect.")
    if user.email == ADMIN_EMAIL:
        raise HTTPException(status_code=409, detail="The admin password is set in the .env file.")
    with SessionLocal.begin() as session:
        session.get(User, user.id).password_hash = hasher.hash(request.new_password)
