"""
seed.py - first-time setup: creates the database, an admin account and (optionally) sample data.

    python seed.py                       create tables + admin account
    python seed.py --sample              also add SAMPLE complaints for demos
    python seed.py --admin-password X    set the admin password to X (min 8 characters)

The admin password is random unless you choose one, and it is saved in ADMIN_LOGIN.txt,
which Git ignores. No password is stored in the source code.

SAMPLE data is made-up demo data. It is not testing evidence.
"""

import argparse
import os
import secrets
import string
from contextlib import closing
from datetime import datetime, timedelta

import auth
import complaints
import database

ADMIN_USERNAME = "admin"
LOGIN_FILE = os.path.join(database.BASE_DIR, "ADMIN_LOGIN.txt")

# (name, contact, category, location, description, urgency, severity, days_ago)
SAMPLE_COMPLAINTS = [
    ("Sample Student 1", "SAMPLE-001", "Electrical Hazard", "Hostel B, corridor 2",
     "Exposed wires hanging near the water cooler sparking when touched by the door.", 5, 5, 0.1),
    ("Sample Student 2", "sample2@example.com", "Water", "Hostel A, ground floor",
     "No water supply in the washrooms since last night.", 5, 4, 0.5),
    ("Sample Student 3", "SAMPLE-003", "Internet", "Library, second floor",
     "Wi-Fi keeps dropping every few minutes, hard to attend online classes.", 3, 3, 1),
    ("Sample Student 4", "sample4@example.com", "Cleanliness", "Canteen",
     "Tables are not wiped after lunch and the floor stays sticky.", 2, 3, 2),
    ("Sample Student 5", "SAMPLE-005", "Furniture", "Classroom 305",
     "Three benches have broken legs and are unsafe to sit on.", 3, 2, 3),
    ("Sample Student 6", "sample6@example.com", "Security", "Main gate",
     "Gate lights are off after 9 pm and visitors are not being checked.", 3, 4, 1.5),
    ("Sample Student 7", "SAMPLE-007", "Transport", "Bus stop near Gate 2",
     "College bus arrives about 20 minutes late most mornings.", 2, 2, 4),
    ("Sample Student 8", "sample8@example.com", "Infrastructure", "Lab 2",
     "Ceiling has a visible crack and plaster fell near a computer desk.", 4, 4, 2.5),
]


def make_password():
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(12))


def ensure_admin(password_choice):
    """Create the admin if missing. Returns the password if one was set or created, else None."""
    if auth.user_exists(ADMIN_USERNAME):
        if password_choice:
            auth.set_password(ADMIN_USERNAME, password_choice)
            return password_choice
        return None
    password = password_choice or make_password()
    auth.create_user("Administrator", ADMIN_USERNAME, password, role="admin")
    return password


def add_sample_data():
    with closing(database.get_connection()) as conn:
        existing = conn.execute("SELECT COUNT(*) FROM complaints").fetchone()[0]
    if existing:
        print(f"Skipped sample data: the database already has {existing} complaint(s).")
        return
    now = datetime.now()
    for name, contact, category, location, text, urgency, severity, days_ago in SAMPLE_COMPLAINTS:
        created = (now - timedelta(days=days_ago)).strftime("%Y-%m-%d %H:%M:%S")
        complaints.create_complaint(
            {"name": name, "contact": contact, "category": category, "location": location,
             "description": text, "urgency": urgency, "severity": severity},
            created_at=created,
        )
    print(f"Added {len(SAMPLE_COMPLAINTS)} SAMPLE complaints.")


def main():
    parser = argparse.ArgumentParser(description="Set up the ComplainSense database.")
    parser.add_argument("--sample", action="store_true", help="add sample complaints (only if none exist)")
    parser.add_argument("--admin-password", help="choose the admin password (min 8 characters)")
    args = parser.parse_args()

    database.init_db()
    print("Database ready:", database.get_db_path())

    password = ensure_admin(args.admin_password)
    if password:
        with open(LOGIN_FILE, "w", encoding="utf-8") as file:
            file.write(f"ComplainSense admin login\nUsername: {ADMIN_USERNAME}\nPassword: {password}\n")
        print(f"Admin login -> username: {ADMIN_USERNAME}   password: {password}")
        print("(also saved in ADMIN_LOGIN.txt, which is not uploaded to GitHub)")
    else:
        print(f"Admin account '{ADMIN_USERNAME}' already exists. Password unchanged.")

    if args.sample:
        add_sample_data()


if __name__ == "__main__":
    main()
