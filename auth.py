"""
auth.py - users, password hashing and login checks.

Passwords are NEVER stored as plain text. We store a "hash": a one-way scrambled
version. At login we scramble what the person typed and compare the two hashes.
"""

import re
import sqlite3
from contextlib import closing

from werkzeug.security import check_password_hash, generate_password_hash

import database
from complaints import ValidationError, clean_text

ROLES = ("admin", "student")
HASH_METHOD = "pbkdf2:sha256"
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_.@\-]{3,50}$")
MIN_PASSWORD_LENGTH = 8

# Used so a wrong username takes about as long as a wrong password.
_DUMMY_HASH = generate_password_hash("not-a-real-password", method=HASH_METHOD)


def _public_user(row):
    """Return user info WITHOUT the password hash."""
    return {
        "user_id": row["user_id"],
        "name": row["name"],
        "username": row["email_or_username"],
        "role": row["role"],
    }


def create_user(name, username, password, role="admin"):
    """Create a user. Raises ValidationError for bad input or a duplicate username."""
    errors = {}
    name = clean_text(name)
    username = clean_text(username)
    if not 2 <= len(name) <= 100:
        errors["name"] = "Name must be 2-100 characters."
    if not USERNAME_PATTERN.match(username):
        errors["username"] = "Username must be 3-50 characters: letters, digits and _ . @ - only."
    if not isinstance(password, str) or len(password) < MIN_PASSWORD_LENGTH:
        errors["password"] = f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
    if role not in ROLES:
        errors["role"] = "Role must be 'admin' or 'student'."
    if errors:
        raise ValidationError(errors)

    password_hash = generate_password_hash(password, method=HASH_METHOD)
    try:
        with closing(database.get_connection()) as conn:
            with conn:  # "with conn" saves (commits) the change, or undoes it on error
                cursor = conn.execute(
                    "INSERT INTO users (name, email_or_username, password_hash, role) VALUES (?, ?, ?, ?)",
                    (name, username, password_hash, role),
                )
                return cursor.lastrowid
    except sqlite3.IntegrityError:
        raise ValidationError({"username": "That username is already taken."})


def authenticate(username, password):
    """Return the user (as a dict) if username + password are right, otherwise None."""
    if not isinstance(username, str) or not isinstance(password, str):
        return None
    with closing(database.get_connection()) as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE email_or_username = ?", (username.strip(),)
        ).fetchone()
    if row is None:
        check_password_hash(_DUMMY_HASH, password)  # waste the same time
        return None
    if not check_password_hash(row["password_hash"], password):
        return None
    return _public_user(row)


def is_admin(user):
    """Only users with the 'admin' role may use the admin panel."""
    return bool(user) and user.get("role") == "admin"


def list_admins():
    """Admins (id + name only) - used for the 'assign to' drop-down."""
    with closing(database.get_connection()) as conn:
        rows = conn.execute(
            "SELECT user_id, name FROM users WHERE role = 'admin' ORDER BY name"
        ).fetchall()
    return [{"user_id": r["user_id"], "name": r["name"]} for r in rows]


def user_exists(username):
    with closing(database.get_connection()) as conn:
        row = conn.execute(
            "SELECT 1 FROM users WHERE email_or_username = ?", (username,)
        ).fetchone()
    return row is not None


def set_password(username, new_password):
    """Change a user's password. Raises ValidationError if too short or the user is unknown."""
    if not isinstance(new_password, str) or len(new_password) < MIN_PASSWORD_LENGTH:
        raise ValidationError({"password": f"Password must be at least {MIN_PASSWORD_LENGTH} characters."})
    with closing(database.get_connection()) as conn:
        with conn:
            cursor = conn.execute(
                "UPDATE users SET password_hash = ? WHERE email_or_username = ?",
                (generate_password_hash(new_password, method=HASH_METHOD), username),
            )
    if cursor.rowcount == 0:
        raise ValidationError({"username": "No such user."})
