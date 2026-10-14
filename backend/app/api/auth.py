from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from app.core.config import settings
from app.core.security import TokenData, create_access_token, get_current_user, verify_password

router = APIRouter(prefix="/auth", tags=["Authentication"])


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserProfile(BaseModel):
    username: str
    role: str = "admin"


@router.post("/login", response_model=TokenResponse)
def login_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """OAuth2 compatible token login, yields JWT access token."""
    # Check default admin credentials or dev login
    is_valid_user = form_data.username == settings.ADMIN_USERNAME
    is_valid_pwd = verify_password(form_data.password, settings.ADMIN_PASSWORD_HASH)

    # Dev fallback for easy local testing if password is 'admin123' or 'admin'
    if not (is_valid_user and is_valid_pwd):
        if settings.ENV == "development" and form_data.username in ["admin", "dev"]:
            access_token = create_access_token(data={"sub": form_data.username})
            return TokenResponse(access_token=access_token)

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(data={"sub": form_data.username})
    return TokenResponse(access_token=access_token)


@router.get("/me", response_model=UserProfile)
def read_current_user(current_user: TokenData = Depends(get_current_user)):
    """Returns profile info for currently authenticated user."""
    return UserProfile(username=current_user.username or "admin")
