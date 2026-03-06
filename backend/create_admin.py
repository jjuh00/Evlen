from motor.motor_asyncio import AsyncIOMotorClient
import sys
import getpass
import asyncio

from config import settings
from utils.authentication import hash_password

async def run() -> None:
    """
    Connect to MongoDB and interactively create or promote an admin user.

    Raises:
        SystemExit: On invalid input or if the user chooses to exit.
    """
    client = AsyncIOMotorClient(settings.mongo_url)
    db = client[settings.mongo_db]

    print("Welcome to the admin user setup")

    # Collect email
    email = input("Admin email address: ").strip().lower()
    if not email or "@" not in email:
        print("ERROR: A valid email address is required", file=sys.stderr)
        client.close()
        sys.exit(1)

    # Check whether this user already exists
    existing = await db["users"].find_one({"email": email})

    if existing:
        # Promote existing user to admin
        current_role = existing.get("role", "user")

        if current_role == "admin":
            print(f"User with email {email} is already an admin")
            client.close()
            return
        
        confirm = input(
            f"User {email} exists with role {current_role},\n"
            "Promote to admin? (y/n): "
        ).strip().lower()

        if confirm != "y":
            print("Aborting without changes")
            client.close()
            return
        
        await db["users"].update_one(
            {"_id": existing["_id"]}, {"$set": {"role": "admin"}}
        )
        print(f"User {email} has been promoted to admin")

    else:
        # Create new admin user
        print(f"No existing user with email {email} found. Creating new admin user")

        display_name = input("Display name (2-30 characters): ").strip()
        if len(display_name) < 2 or len(display_name) > 30:
            print("ERROR: Display name must be between 2 and 30 characters", file=sys.stderr)
            client.close()
            sys.exit(1)

        password = getpass.getpass("Password (minimum 8 characters): ")
        if len(password) < 8:
            print("ERROR: Password must be at least 8 characters long", file=sys.stderr)
            client.close()
            sys.exit(1)

        confirm_password = getpass.getpass("Confirm password: ")
        if password != confirm_password:
            print("ERROR: Passwords don't match", file=sys.stderr)
            client.close()
            sys.exit(1)

        doc = {
            "display_name": display_name,
            "email": email,
            "hashed_password": hash_password(password),
            "role": "admin"
        }
        await db["users"].insert_one(doc)
        print(f"Admin user with email {email} and name {display_name} has been created")

    client.close()

if __name__ == "__main__":
    asyncio.run(run())