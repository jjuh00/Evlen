from pathlib import Path
import secrets
import sys

PLACEHOLDER = "generated_secure_secret_key"
ENV_FILE = Path(".env")
EXAMPLE_ENV_FILE = Path(".env.example")

def load_env_lines(path: Path) -> list[str]:
    """
    Read all lines from given file then return them as a list (newlines).

    Params:
        path: Path to the file to read.

    Returns:
        A list of lines from the file, including newline characters.
    """
    with path.open('r', encoding="utf-8") as f:
        return f.readlines()
    
def write_env_lines(path: Path, lines: list[str]) -> None:
    """
    Write the given lines to the specified file.
    
    Params:
        path: Path to the file to write.
        lines: A list of lines to write to the file, including newline characters.
    """
    with path.open('w', encoding="utf-8") as f:
        f.writelines(lines)

def extract_jwt_secret(lines: list[str]) -> str | None:
    """
    Return the current value of JWT_SECRET or none if not found.

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
    Retrun a copu of lines with the JWT_SECRET line replaced.

    Params:
        lines: A list of lines from the .env file.
        new_secret: The new secret key to set for JWT_SECRET.

    Returns:
        A new list of lines with the JWT_SECRET line replaced with the new secret.
    """
    result = []
    for line in lines:
        if line.strip().startswith("JWT_SECRET="):
            result.append(f"JWT_SECRET={new_secret}\n")
        else:
            result.append(line)
    return result

def main() -> None:
    # Ensure .env exists
    if not ENV_FILE.exists():
        if EXAMPLE_ENV_FILE.exists():
            import shutil
            shutil.copy(EXAMPLE_ENV_FILE, ENV_FILE)
            print(f"Created {ENV_FILE} from {EXAMPLE_ENV_FILE}")
        else:
            # If example .env file doesn't exist, create a minimal .env with placeholder
            minimal = (
                f"JWT_SECRET={PLACEHOLDER}\n",
                "JWT_ALGORITHM=HS256\n",
                "JWT_EXPIRE_MINUTES=120\n",
                "APP_ENV=development\n",
                "MONGO_URL=mongodb://mongo:27017\n",
                "MONGO_DB=evlen\n",
            )
            with ENV_FILE.open('w', encoding="utf-8") as f:
                f.write("".join(minimal))
            print(f"Created minimal {ENV_FILE} with a placeholder")

    # Load current .env lines
    lines = load_env_lines(ENV_FILE)
    current_secret = extract_jwt_secret(lines)

    # Validate the existing secret
    if current_secret is None:
        print("JWT_SECRET not found in .env, appending a generated one")
        new_secret = secrets.token_hex(64)
        lines.append(f"JWT_SECRET={new_secret}\n")
        write_env_lines(ENV_FILE, lines)
        print(f"JWT_SECRET written to {ENV_FILE}")
        return
    
    if current_secret == PLACEHOLDER:
        new_secret = secrets.token_hex(64)
        lines = replace_jwt_secret(lines, new_secret)
        write_env_lines(ENV_FILE, lines)
        print(f"JWT_SECRET generated and written to {ENV_FILE}")
        return
    
    # Secret already looks valid, do length check as a sanity check
    if len(current_secret) < 32:
        print(
            "JWT_SECRET in .env is too short to be secure "
            f"({len(current_secret)} characters but it should be at least 32). "
            "Please update it to a secure random value",
            file=sys.stderr
        )
        sys.exit(1)

    print("JWT_SECRET in .env looks valid, no changes made")

if __name__ == "__main__":
    main()