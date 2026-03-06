from pydantic import BaseModel, EmailStr, Field, field_validator

class UserCreate(BaseModel):
    """
    Data a client submits to create a new user.
    Validated on the way in, but not stored directly in the database.
    """

    display_name: str = Field(
        ...,
        min_length=2,
        max_length=30,
        description="User's public display name"
    )
    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., min_length=8, description="Plain-text password (hashed before storage)")
    confirm_password: str = Field(..., description="Must match the password 'password' field")

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, value: str, info) -> str:
        """
        Validates that the confirm_password field matches the password field.
        """
        if "password" in info.data and value != info.data["password"] :
            raise ValueError("Passwords don't match")
        return value
    
    @field_validator("email")
    @classmethod
    def email_to_lower(cls, value: str) -> str:
        """
        Normalizes email to lowercase to ensure case-insensitive consistency.
        """
        return value.lower()
    
class UserInDB(BaseModel):
    """
    The document structure for a user as stored in the database.
    Contains bcrypt-hashed password and MongoDB's ObjectId as a string.
    """
    
    id: str = Field(..., description="MongoDB _id stringified")
    display_name: str
    email: str
    hashed_password: str
    # "user" role by default
    role: str = "user"
    
class UserPublic(BaseModel):
    """
    Safe representation of a user's public information.
    Doesn't include sensitive fields like password hash.
    """

    id: str
    display_name: str
    email: str
    role: str = "user"

class UserLogin(BaseModel):
    """
    Credentials submitted by a user trying to log in.
    Kept separate from UserCreate so the login route
    reveives only the fields it needs and doesn't have to worry about validation related to registration.
    """

    email: EmailStr
    password: str

    @field_validator("email")
    @classmethod
    def email_to_lower(cls, value: str) -> str:
        """
        Normalizes email to lowercase to ensure case-insensitive consistency.
        """
        return value.lower()