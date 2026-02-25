from passlib.context import CryptContext
from typing import Optional
from datetime import timedelta, datetime, timezone
from jose import jwt, JWTError
from fastapi import HTTPException, status, Response, Cookie, Depends, Request

from config import settings
from models.user import UserPublic

# CryptoContext wraps passlib and lets us easily hash and verify passwords
# bcrypt is the single scheme; deprecated=[] means old hases raise errors
# instead of silently verifying but not rehashing, which is more secure
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    """
    Hash a plain-text password using bcrypt.

    Params:
        password: The plain-text password to hash.

    Returns:
        A bcrypt hash of the password. 
    """
    return _pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    """
    Verify a plain-text password against a bcrypt hash.

    Params:
        plain: The plain-text password to verify.
        hashed: The bcrypt hash to verify against.

    Returns:
        True if the password matches the hash, False otherwise.
    """
    return _pwd_context.verify(plain, hashed)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a signed JWT containing `data` as the payload.

    Params:
        data: A dictionary of data to include in the token payload: typically includes user ID and role.
        expires_delta: Optional timedelta for token expiration. Overrides default expiration if provided.

    Returns:
        A signed JWT as a string (header.payload.signature).
    """
    payload = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.jwt_expire_minutes)
    )
    payload.update({"exp": expire})

    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)

def decode_access_token(token: str) -> dict:
    """
    Decode and verify a JWT, returning the payload if valid.

    Params:
        token: The JWT string to decode.

    Returns:
        The decoded payload as a dictionary if the token is valid.

    Raises:
        HTTPException with 401 status if the token is invalid or expired.
    """
    try:
        payload = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
        return payload
    except JWTError:
        # Covers all JWT-related errors: invalid signature, expired token, malformed token, etc.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session token. Please log in again"
        )
    
# Cookie name
ACCESS_TOKEN_COOKIE = "access_token"

def set_authentication_cookie(response: Response, token: str) -> None:
    """
    Write the JWT into a HTTP-only cookie on `response`.

    Params:
        response: The FastAPI Response object to set the cookie on.
        token: The JWT string to set as the cookie value from create_access_token().
    """
    response.set_cookie(
        key=ACCESS_TOKEN_COOKIE,
        value=token,
        httponly=True, # Blocks JS access (the key security property)
        samesite="lax", # Sent on top-level navigations
        secure=settings.environment == "production", # Only send over HTTPS in production
        max_age=settings.jwt_expire_minutes * 60 # Cookie expiration in seconds
    )

def clear_authentication_cookie(response: Response) -> None:
    """
    Remove the authentication cookie from `response` by setting it with max_age=0.

    Params:
        response: The FastAPI Response object to clear the cookie on.
    """
    response.delete_cookie(
        key=ACCESS_TOKEN_COOKIE,
        httponly=True,
        samesite="lax",
        secure=settings.environment == "production"
    )

async def get_current_user(request: Request, access_token: Optional[str] = Cookie(default=None)) -> UserPublic:
    """
    FastAPI dependency that reads the JWT from the authentication cookie, decodes it, and returns the current user's information.
    Injected on routes that require authentication.
    
    Params:
        request: The FastAPI Request object
        access_token: Valie of `access_token` cookie; None if cookie is missing.

    Returns:
        UserPublic: A Pydantic model containing the user's public information (id, display_name, email, role).

    Raises:
        HTTPException with 401 status if the token is missing, invalid, or expired.
    """
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    payload = decode_access_token(access_token)

    # Validate the expected claims are present in the token payload
    user_id: str = payload.get("sub")
    role: str = payload.get("role", "user")
    display_name: str = payload.get("display_name", "")
    email: str = payload.get("email", "")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token payload. Please log in again"
        )
    
    return UserPublic(
        id=user_id,
        display_name=display_name,
        email=email,
        role=role
    )

async def get_optional_user(access_token: Optional[str] = Cookie(default=None)) -> Optional[UserPublic]:
    """
    Similar to get_current_user but returns None instead of raising an exception if the token is missing or invalid.
    Used on public pages where it's useful to know if the user is logged in but not required.

    Params:
        access_token: Value of `access_token` cookie; None if cookie is missing.
    Returns:
        UserPublic: The current user's information if a valid token is present, or None if not authenticated.
    """
    if not access_token:
        return None
    try:
        return await get_current_user(
            request=None, access_token=access_token
        )
    except HTTPException:
        return None