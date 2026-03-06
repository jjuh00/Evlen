from pathlib import Path
import os
import shutil
import secrets
import sys

PLACEHOLDER = "generated_secure_secret_key"

# Both filtes live in this directry
_SCRIPT_DIR = Path(__file__).parent
ENV_FILE = _SCRIPT_DIR / ".env"
EXAMPLE_ENV_FILE = _SCRIPT_DIR / ".env.example"

def load_env_files(path: Path) -> list[str]:
    """
    Real all lines from the given file and return them as a list.

    Params:
        path: Path to the file to read.

    Returns:
        A list of lines from the file.
    """
    with path.open("r", encoding="utf-8") as f:
        return f.readlines()
    
def write_env_files(path: Path, lines: list[str]) -> None:
    """
    Write a list of lines to the given file.

    Params:
        path: Path to the file to write.
        lines: A list of lines to write to the file.
    """
    with path.open("w", encoding="utf-8") as f:
        f.writelines(lines)

def extract_jwt_secret(lines: list[str]) -> str | None:
    """
    Return the current value of JWT_SECRET from .env or None if not found.

    Params:
        lines: A list of lines from the .env file.

    Returns:
        The current JWT_SECRET value as a string, or None if not found.
    """
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("JWT_SECRET="):
            return stripped.split("=", 1)[1].strip()
    return None

def replace_jwt_secret(lines: list[str], new_secret: str) -> list[str]:
    """
    Return a copy of lines with the JWT_SECRET line replaced by the new secret.

    Params:
        lines: A list of lines from the .env file.
        new_secret: The new secret key to set for JWT_SECRET.

    Returns:
        A new list of lines with the JWT_SECRET line replaced with the new secret.    
    """
    return [
        f"JWT_SECRET={new_secret}\n" if line.strip().startswith("JWT_SECRET") else line
        for line in lines
    ]

def main() -> None:
    """
    Skip all file work if JWT_SECRET is already set in the process environment. Otherwise,
    ensure backend/.env exists and contains a secure JWT_SECRET, generating a new one if needed.
    """
    # In Docker the env var is injected directly
    env_secret = os.environ.get("JWT_SECRET", "")
    if env_secret and env_secret != PLACEHOLDER and len(env_secret) >= 32:
        print("JWT_SECRET is already set in the environment, skipping .env generation")
        return

    # Ensure .env exists
    if not ENV_FILE.exists():
        if EXAMPLE_ENV_FILE.exists():
            shutil.copy(EXAMPLE_ENV_FILE, ENV_FILE)
            print(f"Created {ENV_FILE} from {EXAMPLE_ENV_FILE}")
        else:
            # Fallback: create a minimal .env with the placeholder if .env.example is missing
            minimal = (
                f"JWT_SECRET={PLACEHOLDER}\n",
                "JWT_ALGORITHM=HS256\n",
                "JWT_EXPIRE_MINUTES=120\n",
                "APP_ENV=development\n",
                "MONGO_URL=mongodb://mongo:27017\n",
                "MONGO_DB=evlen\n"
            )
            write_env_files(ENV_FILE, list(minimal))
            print(f"Created minimal {ENV_FILE} with a placeholder (no .env.example found)")

    # Validate and generate the secret
    lines = load_env_files(ENV_FILE)
    current_secret = extract_jwt_secret(lines)

    if current_secret is None:
        # Key is missing entirely, add it
        new_secret = secrets.token_hex(64)
        lines.append(f"JWT_SECRET={new_secret}\n")
        write_env_files(ENV_FILE, lines)
        print(f"JWT_SECRET was missing and has been generated and added to {ENV_FILE}")
        return
    
    if current_secret == PLACEHOLDER:
        # Key is the placeholder, replace it
        new_secret = secrets.token_hex(64)
        lines = replace_jwt_secret(lines, new_secret)
        write_env_files(ENV_FILE, lines)
        print(f"JWT_SECRET was the placeholder and has been replaced with a generated secret in {ENV_FILE}")
        return

    # Sanity-check an existing secret for minimum length
    if len(current_secret) < 32:
        print(
            f"WARNING: JWT_SECRET in {ENV_FILE} is only {len(current_secret)} characters long, which is too short to be secure "
            "(minimum is 32 characters). Please replace it with a secure random value",
            file=sys.stderr
        )
        sys.exit(1)

    print(f"JWT_SECRET in {ENV_FILE} looks valid, no changes made")

if __name__ == "__main__":
    main()