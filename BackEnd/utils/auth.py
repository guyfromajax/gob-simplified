"""
Authentication Utilities

Provides password hashing, JWT token management, and auth dependencies.

USAGE:
    from BackEnd.utils.auth import (
        hash_password,
        verify_password,
        create_access_token,
        get_current_user,
        get_current_user_optional
    )

    # Hash password for storage
    hashed = hash_password("user_password")
    
    # Verify password on login
    if verify_password("user_password", hashed):
        token = create_access_token({"sub": user_id, "email": email})
    
    # Protect endpoint (requires auth)
    @app.get("/protected")
    async def protected(user: dict = Depends(get_current_user)):
        return {"user_id": user["user_id"]}
    
    # Optional auth (returns None if not authenticated)
    @app.get("/public")
    async def public(user: dict = Depends(get_current_user_optional)):
        if user:
            return {"user_id": user["user_id"]}
        return {"message": "anonymous"}
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from BackEnd.db import users_collection


# JWT Configuration
# In production, set JWT_SECRET_KEY as environment variable
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = int(os.getenv("JWT_EXPIRATION_HOURS", "24"))

# Security scheme for FastAPI docs
security = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.
    
    Args:
        password: Plain text password
        
    Returns:
        Hashed password string
    """
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def verify_password(password: str, hashed: str) -> bool:
    """
    Verify a password against its hash.
    
    Args:
        password: Plain text password to verify
        hashed: Hashed password from database
        
    Returns:
        True if password matches, False otherwise
    """
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    except Exception:
        return False


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token.
    
    Args:
        data: Payload data (should include 'sub' for user_id)
        expires_delta: Optional custom expiration time
        
    Returns:
        JWT token string
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS)
    
    to_encode.update({"exp": expire})
    
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> Optional[dict]:
    """
    Decode and validate a JWT token.
    
    Args:
        token: JWT token string
        
    Returns:
        Decoded payload dict or None if invalid
    """
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """
    FastAPI dependency to get the current authenticated user.
    Raises 401 if not authenticated.
    
    Usage:
        @app.get("/protected")
        async def protected(user: dict = Depends(get_current_user)):
            return {"user_id": user["user_id"]}
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    payload = decode_token(credentials.credentials)
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Return user info from token (avoids DB lookup on every request)
    return {
        "user_id": user_id,
        "email": payload.get("email"),
        "role": payload.get("role", "user")
    }


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Optional[dict]:
    """
    FastAPI dependency to optionally get the current user.
    Returns None if not authenticated (doesn't raise error).
    
    Usage:
        @app.get("/public")
        async def public(user: dict = Depends(get_current_user_optional)):
            if user:
                return {"user_id": user["user_id"]}
            return {"message": "anonymous"}
    """
    if not credentials:
        return None
    
    payload = decode_token(credentials.credentials)
    
    if not payload:
        return None
    
    user_id = payload.get("sub")
    if not user_id:
        return None
    
    return {
        "user_id": user_id,
        "email": payload.get("email"),
        "role": payload.get("role", "user")
    }


async def get_admin_user(user: dict = Depends(get_current_user)) -> dict:
    """
    FastAPI dependency that requires admin role.
    Raises 403 if user is not an admin.
    
    Usage:
        @app.get("/admin-only")
        async def admin_only(user: dict = Depends(get_admin_user)):
            return {"admin": True}
    """
    if user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return user


def get_user_by_email(email: str) -> Optional[dict]:
    """
    Get a user document by email.
    
    Args:
        email: User's email address
        
    Returns:
        User document or None if not found
    """
    return users_collection.find_one({"email": email.lower()})


def get_user_by_id(user_id: str) -> Optional[dict]:
    """
    Get a user document by ID.
    
    Args:
        user_id: User's ID (string)
        
    Returns:
        User document or None if not found
    """
    from bson import ObjectId
    try:
        return users_collection.find_one({"_id": ObjectId(user_id)})
    except Exception:
        return None
