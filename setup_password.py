"""
setup_password.py
Utility to generate a bcrypt hash for ADMIN_PASSWORD_HASH in .env

Usage:
    python setup_password.py

Paste the output into your .env file as ADMIN_PASSWORD_HASH=<hash>
"""
import getpass
import sys

try:
    import bcrypt
except ImportError:
    print("ERROR: bcrypt is not installed. Run: pip install bcrypt")
    sys.exit(1)


def main():
    print("=" * 50)
    print("Admin Password Setup")
    print("=" * 50)
    print("This generates a bcrypt hash to store in your .env file.")
    print("The plain text password is NOT stored anywhere.\n")

    pwd = getpass.getpass("Enter new admin password: ")
    if len(pwd) < 8:
        print("ERROR: Password must be at least 8 characters.")
        sys.exit(1)

    confirm = getpass.getpass("Confirm password: ")
    if pwd != confirm:
        print("ERROR: Passwords do not match.")
        sys.exit(1)

    hashed = bcrypt.hashpw(pwd.encode(), bcrypt.gensalt(rounds=12)).decode()
    print(f"\nAdd this line to your .env file:\n")
    print(f"ADMIN_PASSWORD_HASH={hashed}")
    print("\nDo NOT share this file or commit it to version control.")


if __name__ == "__main__":
    main()
