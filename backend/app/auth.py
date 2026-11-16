"""Accounts: sign up, log in, roles, and the logged-in user's own settings."""
import logging
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from app.config import ADMIN_EMAIL, ADMIN_PASSWORD, JWT_EXPIRE_MINUTES, JWT_SECRET
from app.db import SessionLocal, User
from app.ml_client import location_names
from app.realtime import clear_failed_logins, record_failed_login, too_many_failed_logins
from app.sms import normalise_phone

log = logging.getLogger("uvicorn.error")
router = APIRouter(prefix="/api")

JWT_ALGORITHM = "HS256"
hasher = PasswordHasher()
bearer = HTTPBearer(auto_error=False)

# Checked when an email has no account, so that login takes the same time either way and
# can't be used to find out who has an account
UNKNOWN_USER_HASH = hasher.hash("no account has this password")


class RegisterRequest(BaseModel):
    """Public sign-up. There is deliberately no is_admin field: extra fields are ignored."""

    phone: str = Field(max_length=32)
    email: EmailStr | None = None
    password: str = Field(min_length=8, max_length=128)
    home_location: str | None = None


class LoginRequest(BaseModel):
    login: str = Field(max_length=254)  # a phone number or an email address
    password: str = Field(max_length=128)


class HomeRequest(BaseModel):
    home_location: str | None


class ContactRequest(BaseModel):
    phone: str | None = Field(default=None, max_length=32)
    email: EmailStr | None = None


class PasswordRequest(BaseModel):
    current_password: str = Field(max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


def password_matches(password_hash, password):
    try:
        return hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def seed_admin():
    """Create the admin account from .env, or bring it into line if .env has changed.

    This is the only place that ever makes an account an admin, and there is exactly one admin:
    the account whose email is ADMIN_EMAIL. Any other account marked admin is demoted here.
    """
    with SessionLocal.begin() as session:
        demoted = session.execute(
            update(User).where(User.is_admin, User.email.is_distinct_from(ADMIN_EMAIL)).values(is_admin=False)
        ).rowcount
        if demoted:
            log.warning("Removed admin rights from %d account(s) that aren't ADMIN_EMAIL.", demoted)
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
    return email.strip().lower() if email else None


def required_phone(text):
    phone = normalise_phone(text)
    if phone is None:
        raise HTTPException(status_code=422, detail="Enter a Kenyan mobile number, for example 0712 345 678.")
    return phone


def check_location(name):
    if name is not None and name not in location_names():
        raise HTTPException(status_code=422, detail=f"Unknown location: {name}")


def check_contact_free(session, phone, email, user=None):
    """Phone numbers and emails each belong to one account. The admin email is reserved, so
    nobody can take it before the admin account exists, or if ADMIN_EMAIL changes."""
    if email and email == ADMIN_EMAIL and not (user and user.is_admin):
        raise HTTPException(status_code=409, detail="An account with this email already exists.")
    user_id = user.id if user else 0
    for column, value, label in ((User.phone, phone, "phone number"), (User.email, email, "email")):
        if value and session.scalar(select(User.id).where(column == value, User.id != user_id)):
            raise HTTPException(status_code=409, detail=f"An account with this {label} already exists.")


def user_data(user):
    return {
        "id": user.id,
        "phone": user.phone,
        "email": user.email,
        "home_location": user.home_location,
        "is_admin": user.is_admin,
    }


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
    """Every account made here is an ordinary user. Only seed_admin() makes the admin."""
    check_location(request.home_location)
    phone = required_phone(request.phone)
    email = normalise_email(request.email)
    user = User(
        phone=phone,
        email=email,
        password_hash=hasher.hash(request.password),
        home_location=request.home_location,
        is_admin=False,
        last_login_at=func.now(),  # signing up also logs the user in
    )
    try:
        with SessionLocal.begin() as session:
            check_contact_free(session, phone, email)
            session.add(user)
            session.flush()
            return login_response(user)
    except IntegrityError:  # two sign-ups with the same details at the same moment
        raise HTTPException(status_code=409, detail="An account with this phone number or email already exists.")


@router.post("/auth/login")
def login(body: LoginRequest, request: Request):
    """Log in with a phone number or an email address."""
    text = body.login.strip()
    if "@" in text:
        identifier, column = normalise_email(text), User.email
    else:
        identifier, column = normalise_phone(text) or text, User.phone
    # nginx sets X-Real-IP. Limiting by login and address together means an attacker elsewhere
    # can't lock someone out of their own account.
    limit_key = f"{identifier}:{request.headers.get('x-real-ip') or request.client.host}"
    if too_many_failed_logins(limit_key):
        raise HTTPException(status_code=429, detail="Too many failed attempts. Try again in 15 minutes.")

    with SessionLocal() as session:
        user = session.scalar(select(User).where(column == identifier))
    if not password_matches(user.password_hash if user else UNKNOWN_USER_HASH, body.password) or user is None:
        record_failed_login(limit_key)
        # The same message for both cases, so it doesn't reveal who has an account
        raise HTTPException(status_code=401, detail="Incorrect phone number, email or password.")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="This account has been disabled.")
    clear_failed_logins(limit_key)
    with SessionLocal.begin() as session:
        session.execute(update(User).where(User.id == user.id).values(last_login_at=func.now()))
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


@router.put("/me/contact")
def update_contact(request: ContactRequest, user: User = Depends(current_user)):
    """Change the phone number and email. Users need a phone number; the admin's email is fixed."""
    phone = normalise_phone(request.phone) if request.phone else None
    if request.phone and phone is None:
        required_phone(request.phone)  # raises the friendly error
    email = normalise_email(request.email)
    if user.is_admin:
        email = user.email  # set in .env, not here
    elif phone is None:
        raise HTTPException(status_code=422, detail="A phone number is required for SMS alerts.")
    try:
        with SessionLocal.begin() as session:
            check_contact_free(session, phone, email, user=user)
            stored = session.get(User, user.id)
            stored.phone, stored.email = phone, email
            return user_data(stored)
    except IntegrityError:
        raise HTTPException(status_code=409, detail="An account with this phone number or email already exists.")


@router.post("/me/password", status_code=204)
def change_password(request: PasswordRequest, user: User = Depends(current_user)):
    if not password_matches(user.password_hash, request.current_password):
        raise HTTPException(status_code=403, detail="Your current password is incorrect.")
    if user.email == ADMIN_EMAIL:
        raise HTTPException(status_code=409, detail="The admin password is set in the .env file.")
    with SessionLocal.begin() as session:
        session.get(User, user.id).password_hash = hasher.hash(request.new_password)
