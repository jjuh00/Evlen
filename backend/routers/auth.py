from fastapi import APIRouter, status, Request, Depends, Response, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from motor.motor_asyncio import AsyncIOMotorDatabase

from models.user import UserPublic
from utils.authentication import (
    get_optional_user,
    hash_password,
    create_access_token,
    set_authentication_cookie,
    clear_authentication_cookie
)
from database import get_database

router = APIRouter(prefix="/auth", tags=["auth"])
templates = Jinja2Templates(directory="/frontend/templates")

# Helpers
def _error_message_html(message: str) -> HTMLResponse:
    """
    Wrap an error meessage in the HTML fragment HTMX can swap into the page.

    Params:
        message: The error message to display to the user.

    Returns:
        HTMLResponse: An HTML fragment containing the error message
    """
    # The 'fade-in' class triggers the CSS animation
    safe = message.replace("<", "&lt").replace(">", "&gt;")
    return HTMLResponse(
        content=f'<p class="error-message fade-in">{safe}</p>',
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT
    )

# GET /auth/login
# Renders the login/register page
@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, current_user: UserPublic | None = Depends(get_optional_user)):
    """
    Serve the login.html template.

    Params:
        request: FastAPI Request object
        current_user: The currently logged in user, if any. Injected by the get_optional_user dependency.

    Returns:
        Rendered login.html. If the user is already logged in, 
        redirect them to the homepage.
    """
    if current_user:
        # User is already logged in, no need to show login page
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "current_user": None}
    )

# POST /auth/register
@router.post("/register", response_class=HTMLResponse)
async def register(
    response: Response,
    display_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Create a new user accounnt. Validates the input, checks for existing email, hashes the password, and stores the user in the database.

    Params:
        response: FastAPI Response object, used to set the authentication cookie on successful registration.
        display_name: The user's display name.
        email: The user's email address, must be unique.
        password: The user's plain-text password (before hashing).
        confirm_password: Confirmation of the user's password. Must match `password`.
        db: The Motor database instance, injected by the get_database dependency.

    Returns:
        On success: 200 HTML fragment that triggers HTMX redirect to the "/".
        On failure: 422 HTML fragment containing the error message to display to the user.
    """
    # Normalize email to match the lookup convention
    email = email.strip().lower()

    # Cross-field validation
    if password != confirm_password:
        return _error_message_html("Passwords do not match")
    
    if len(password) < 8:
        return _error_message_html("Password must be at least 8 characters long")
    
    display_name = display_name.strip()
    if len(display_name) < 2:
        return _error_message_html("Display name must be at least 2 characters long")
    
    # Unique email check to prevent duplicate accounts
    existing_email = await db["users"].find_one({"email": email})
    if existing_email:
        return _error_message_html("An account with this email already exists")
    
    # Persist the new user
    doc = {
        display_name: display_name,
        email: email,
        "hashed_password": hash_password(password),
        "role": "user"
    }
    result = await db["users"].insert_one(doc)
    user_id = str(result.inserted_id)

    # Issue JWT and set cookie
    token = create_access_token({
        "sub": user_id,
        "display_name": display_name,
        "email": email,
        "role": "user"
    })
    set_authentication_cookie(response, token)

    # Tell HTMX to redirect to homepage
    # HX-Redict makes HTMX perfom a client-side redirect to the specified URL after successful response
    response.headers["HX-Redirect"] = "/"
    return HTMLResponse(content="", status_code=status.HTTP_200_OK)

# POST /auth/login
@router.post("/login", response_class=HTMLResponse)
async def login(
    response: Response,
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Authenticate a user with their email and password. Validates the credentials, and if correct, issues a JWT and sets the authentication cookie.

    Params:
        response: FastAPI Response object, used to set the authentication cookie on successful login.
        email: The user's email address.
        password: The user's plain-text password from the login form.
        db: The Motor database instance, injected by the get_database dependency.

    Returns:
        On success: 200 HTML fragment that triggers HTMX redirect to the "/".
        On failure: 422 HTML fragment containing the error message to display to the user.
    """
    email = email.strip().lower()

    # Look up the user by email
    user_doc = await db["users"].find_one({"email": email})
    if not user_doc:
        # Use the same error message as invalid password to avoid giving hints about which emails are registered
        return _error_message_html("Invalid email or password")
    
    # Verify the password
    if not hash_password.verify(password, user_doc["hashed_password"]):
        return _error_message_html("Invalid email or password")
    
    # Issue JWT and set cookie
    user_id = str(user_doc["_id"])
    token = create_access_token({
        "sub": user_id,
        "display_name": user_doc["display_name"],
        "email": user_doc["email"],
        "role": user_doc.get("role", "user")
    })
    set_authentication_cookie(response, token)

    # Tell HTMX to redirect to homepage
    response.headers["HX-Redirect"] = "/"
    return HTMLResponse(content="", status_code=status.HTTP_200_OK)

# POST /auth/logout
@router.post("/logout", response_class=HTMLResponse)
async def logout():
    """
    Log the user out by clearing the authentication cookie.

    Returns:
        A redirect to "/" (works with HTMX to redirect the user to the homepage after logout).
    """
    # Build a redirect response then mutatie it to clear the cookie before returning
    # RedirectResponse cannot be returned directly because we need to clear the cookie on the response object first
    redirect = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    clear_authentication_cookie(redirect)

    # Support HTMX-initiated logout by also sending the HX-Redirect header
    # This ensures that after logout, HTMX will redirect the user to the homepage
    redirect.headers["HX-Redirect"] = "/"
    return redirect