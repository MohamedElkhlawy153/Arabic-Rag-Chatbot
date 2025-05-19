# backend/app/api/v1/endpoints/auth.py
import logging
from fastapi import APIRouter, Depends, HTTPException, status, Body

# from fastapi.security import OAuth2PasswordRequestForm # If using form data

from ....core import security
from ....core.config import settings
from ....schemas import auth as auth_schemas  # Use your auth schemas

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/login",
    response_model=auth_schemas.LoginResponse,  # Use the schema that includes token and user
    summary="Admin Login",
    description="Authenticates an admin user and returns an access token and user details.",
)
async def login_for_access_token(
    # Expects a JSON body matching UserLoginRequest schema
    login_request: auth_schemas.UserLoginRequest = Body(...),
    # If you prefer form data (e.g., from a standard HTML form POST):
    # form_data: OAuth2PasswordRequestForm = Depends()
    # And then use form_data.username and form_data.password
):
    # Verify against the hardcoded admin credentials from settings
    is_correct_password = security.verify_password(
        login_request.password, settings.ADMIN_PASSWORD
    )
    if not (login_request.username == settings.ADMIN_USERNAME and is_correct_password):
        logger.warning(f"Failed login attempt for username: {login_request.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},  # Standard for token-based auth
        )

    # Create JWT token. The 'sub' (subject) claim is typically the username.
    access_token = security.create_access_token(
        data={"sub": login_request.username}
        # You can add other claims like roles here if needed: "roles": ["admin"]
    )
    logger.info(f"Admin user '{login_request.username}' logged in successfully.")

    # Prepare the response
    user_details = auth_schemas.UserAuthDetails(username=login_request.username)
    token_details = auth_schemas.Token(access_token=access_token, token_type="bearer")

    return auth_schemas.LoginResponse(token=token_details, user=user_details)
