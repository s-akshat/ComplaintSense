"""
complaints.py - the business logic for complaints.

Create / Read / Update / Delete (CRUD):
    Create -> create_complaint()
    Read   -> get_public_status(), get_complaint_admin(), list_complaints()
    Update -> update_complaint()
    Delete -> delete_complaint()

Every SQL query uses "?" placeholders and passes the values separately.
This is called a PARAMETERISED query and it stops SQL injection attacks.
"""

import re
import secrets
import sqlite3
from contextlib import closing
from datetime import datetime

import database
import priority

CATEGORIES = [
    "Electricity", "Electrical Hazard", "Water", "Cleanliness", "Infrastructure",
    "Internet", "Furniture", "Security", "Fire Safety", "Medical", "Transport", "Other",
]
STATUSES = ["Pending", "In Progress", "Resolved"]

MAX_REMARKS = 500
ID_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I so IDs are easy to read out
ID_PATTERN = re.compile(r"^CS-\d{8}-[A-Z0-9]{5}$")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
STUDENT_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9\-/]{2,29}$")
CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# ORDER BY text comes from this fixed dictionary, never from user input.
SORT_OPTIONS = {
    "priority": "priority_score DESC, created_at ASC, rowid ASC",   # highest first, ties: oldest first
    "newest": "created_at DESC, rowid DESC",
    "oldest": "created_at ASC, rowid ASC",
    "status": "CASE status WHEN 'Pending' THEN 0 WHEN 'In Progress' THEN 1 ELSE 2 END, "
              "priority_score DESC, created_at ASC, rowid ASC",
}

_KEEP = object()  # marker meaning "do not change this field"


class ValidationError(ValueError):
    """Bad input. `errors` is a dictionary: field name -> message."""

    def __init__(self, errors):
        self.errors = errors
        super().__init__("; ".join(errors.values()))


class NotFoundError(LookupError):
    """The complaint (or user) does not exist."""


# ---------- small helpers ----------

def now_string():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def clean_text(value):
    """Turn input into safe, trimmed text: non-strings become '', control characters are removed."""
    if not isinstance(value, str):
        return ""
    return CONTROL_CHARS.sub("", value).strip()


def _row_to_dict(row):
    data = dict(row)
    if "needs_immediate_review" in data:
        data["needs_immediate_review"] = bool(data["needs_immediate_review"])
    return data


def generate_complaint_id():
    """Make an ID like CS-20261029-K7M2Q (date + 5 random characters)."""
    random_part = "".join(secrets.choice(ID_ALPHABET) for _ in range(5))
    return f"CS-{datetime.now():%Y%m%d}-{random_part}"


def normalise_complaint_id(complaint_id):
    """Trim and upper-case an ID typed by a person. Returns None if it is not shaped like an ID."""
    if not isinstance(complaint_id, str):
        return None
    candidate = complaint_id.strip().upper()
    return candidate if ID_PATTERN.match(candidate) else None


# ---------- validation ----------

def validate_complaint_input(data):
    """Check and clean the submitted form. Returns a clean dictionary or raises ValidationError."""
    errors = {}
    name = clean_text(data.get("name"))
    contact = clean_text(data.get("contact"))
    category = clean_text(data.get("category"))
    description = clean_text(data.get("description"))
    location = clean_text(data.get("location"))

    if not 2 <= len(name) <= 100:
        errors["name"] = "Name must be 2-100 characters."

    if "@" in contact:
        if len(contact) > 100 or not EMAIL_PATTERN.match(contact):
            errors["contact"] = "Please enter a valid email address."
    elif not STUDENT_ID_PATTERN.match(contact):
        errors["contact"] = "Enter a valid email or a student ID (3-30 letters, digits, - or /)."

    if category not in CATEGORIES:
        errors["category"] = "Please choose a category from the list."

    if len(description) < 10:
        errors["description"] = "Description must be at least 10 characters."
    elif len(description) > 1000:
        errors["description"] = "Description must be at most 1000 characters."

    if not 2 <= len(location) <= 100:
        errors["location"] = "Location must be 2-100 characters."

    urgency = severity = None
    try:
        urgency = priority.validate_rating(data.get("urgency"), "urgency")
    except ValueError as err:
        errors["urgency"] = str(err)
    try:
        severity = priority.validate_rating(data.get("severity"), "severity")
    except ValueError as err:
        errors["severity"] = str(err)

    if errors:
        raise ValidationError(errors)

    return {
        "name": name, "contact": contact, "category": category,
        "description": description, "location": location,
        "urgency": urgency, "severity": severity,
    }


# ---------- Create ----------

def create_complaint(data, created_at=None):
    """Validate, score and save a new complaint. Returns the new ID and its priority.

    `created_at` is only used by seed.py to make sample data with different dates.
    """
    clean = validate_complaint_input(data)
    result = priority.evaluate_complaint(clean["urgency"], clean["severity"], clean["category"])
    timestamp = created_at or now_string()

    with closing(database.get_connection()) as conn:
        for _ in range(10):  # in the (very unlikely) case of an ID clash, try a new ID
            complaint_id = generate_complaint_id()
            try:
                with conn:  # one transaction: both inserts succeed or neither does
                    conn.execute(
                        """INSERT INTO complaints
                           (complaint_id, complainant_name, contact, category, description, location,
                            urgency, severity, priority_score, priority_level, needs_immediate_review,
                            status, created_at, updated_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Pending', ?, ?)""",
                        (complaint_id, clean["name"], clean["contact"], clean["category"],
                         clean["description"], clean["location"], clean["urgency"], clean["severity"],
                         result["priority_score"], result["priority_level"],
                         int(result["needs_immediate_review"]), timestamp, timestamp),
                    )
                    conn.execute(
                        """INSERT INTO complaint_updates
                           (complaint_id, old_status, new_status, updated_by, update_time, remarks)
                           VALUES (?, NULL, 'Pending', NULL, ?, 'Complaint submitted')""",
                        (complaint_id, timestamp),
                    )
                return {"complaint_id": complaint_id, **result}
            except sqlite3.IntegrityError:
                continue
    raise RuntimeError("Could not generate a unique complaint ID. Please try again.")


# ---------- Read ----------

def get_history(complaint_id, public=False):
    """Return the status history, oldest first.

    public=True returns only STATUS CHANGES, without staff names or internal notes,
    which is what the person tracking their complaint is allowed to see.
    """
    query = """SELECT u.update_id, u.old_status, u.new_status, u.update_time, u.remarks,
                      usr.name AS updated_by_name
               FROM complaint_updates u
               LEFT JOIN users usr ON usr.user_id = u.updated_by
               WHERE u.complaint_id = ?"""
    if public:
        query += " AND (u.old_status IS NULL OR u.old_status != u.new_status)"
    query += " ORDER BY u.update_id ASC"

    with closing(database.get_connection()) as conn:
        rows = conn.execute(query, (complaint_id,)).fetchall()

    history = []
    for row in rows:
        item = {
            "old_status": row["old_status"], "new_status": row["new_status"],
            "time": row["update_time"], "remarks": row["remarks"] or "",
        }
        if not public:
            item["updated_by"] = row["updated_by_name"] or "System"
        history.append(item)
    return history


def get_public_status(complaint_id):
    """What the person who filed the complaint may see: no name, contact or staff details."""
    cid = normalise_complaint_id(complaint_id)
    if cid is None:
        raise NotFoundError("No complaint found with that ID.")
    with closing(database.get_connection()) as conn:
        row = conn.execute(
            """SELECT complaint_id, category, status, priority_score, priority_level,
                      needs_immediate_review, created_at, updated_at
               FROM complaints WHERE complaint_id = ?""",
            (cid,),
        ).fetchone()
    if row is None:
        raise NotFoundError("No complaint found with that ID.")
    data = _row_to_dict(row)
    data["history"] = get_history(cid, public=True)
    return data


def get_complaint_admin(complaint_id):
    """Full details (for administrators only), including who it is assigned to."""
    cid = normalise_complaint_id(complaint_id)
    if cid is None:
        raise NotFoundError("No complaint found with that ID.")
    with closing(database.get_connection()) as conn:
        row = conn.execute(
            """SELECT c.*, a.name AS assigned_to_name
               FROM complaints c LEFT JOIN users a ON a.user_id = c.assigned_to
               WHERE c.complaint_id = ?""",
            (cid,),
        ).fetchone()
    if row is None:
        raise NotFoundError("No complaint found with that ID.")
    data = _row_to_dict(row)
    data["history"] = get_history(cid, public=False)
    return data


def list_complaints(status=None, category=None, level=None, search=None, sort="priority"):
    """Return complaints (admin view), filtered and sorted.

    Default sort: highest priority score first; equal scores -> oldest first.
    """
    if sort not in SORT_OPTIONS:
        raise ValidationError({"sort": "Unknown sort option."})

    conditions, params = [], []
    if status:
        conditions.append("c.status = ?")
        params.append(status)
    if category:
        conditions.append("c.category = ?")
        params.append(category)
    if level:
        conditions.append("c.priority_level = ?")
        params.append(level.upper() if isinstance(level, str) else level)
    if search and clean_text(search):
        text = clean_text(search).replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{text}%"
        conditions.append(
            "(c.complaint_id LIKE ? ESCAPE '\\' OR c.description LIKE ? ESCAPE '\\' "
            "OR c.location LIKE ? ESCAPE '\\' OR c.category LIKE ? ESCAPE '\\' "
            "OR c.complainant_name LIKE ? ESCAPE '\\')"
        )
        params.extend([pattern] * 5)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    # SORT_OPTIONS values contain unqualified column names; "c." is not needed because
    # only the complaints table has them in this query except user name (aliased below).
    query = f"""SELECT c.*, a.name AS assigned_to_name
                FROM complaints c LEFT JOIN users a ON a.user_id = c.assigned_to
                {where}
                ORDER BY {SORT_OPTIONS[sort].replace('rowid', 'c.rowid')}"""

    with closing(database.get_connection()) as conn:
        rows = conn.execute(query, params).fetchall()
    return [_row_to_dict(r) for r in rows]


# ---------- Update ----------

def update_complaint(complaint_id, admin_id, new_status=None, remarks=None, assigned_to=_KEEP):
    """Change the status, add a remark and/or assign the complaint to an administrator.

    Every change is written to complaint_updates so there is a full history.
    Rule for the public tracking page: only STATUS CHANGES are shown to the complainant.
    """
    cid = normalise_complaint_id(complaint_id)
    if cid is None:
        raise NotFoundError("No complaint found with that ID.")

    remarks = clean_text(remarks)
    if len(remarks) > MAX_REMARKS:
        raise ValidationError({"remarks": f"Remarks must be at most {MAX_REMARKS} characters."})
    if new_status is not None and new_status not in STATUSES:
        raise ValidationError({"status": "Status must be one of: " + ", ".join(STATUSES) + "."})

    with closing(database.get_connection()) as conn:
        row = conn.execute("SELECT * FROM complaints WHERE complaint_id = ?", (cid,)).fetchone()
        if row is None:
            raise NotFoundError("No complaint found with that ID.")

        old_status = row["status"]
        status = old_status if new_status is None else new_status

        new_assignee = row["assigned_to"]
        assignee_name = None
        if assigned_to is not _KEEP:
            if assigned_to in (None, ""):
                new_assignee = None
            else:
                try:
                    wanted = int(assigned_to)
                except (TypeError, ValueError):
                    raise ValidationError({"assigned_to": "Invalid person selected."})
                admin = conn.execute(
                    "SELECT user_id, name FROM users WHERE user_id = ? AND role = 'admin'", (wanted,)
                ).fetchone()
                if admin is None:
                    raise ValidationError({"assigned_to": "That person cannot be assigned complaints."})
                new_assignee, assignee_name = admin["user_id"], admin["name"]

        status_changed = status != old_status
        assignment_changed = new_assignee != row["assigned_to"]
        if not (status_changed or assignment_changed or remarks):
            raise ValidationError({"update": "Nothing to update: change the status, add a remark or assign it."})

        timestamp = now_string()
        with conn:
            conn.execute(
                "UPDATE complaints SET status = ?, assigned_to = ?, updated_at = ? WHERE complaint_id = ?",
                (status, new_assignee, timestamp, cid),
            )
            if status_changed or remarks:
                conn.execute(
                    """INSERT INTO complaint_updates
                       (complaint_id, old_status, new_status, updated_by, update_time, remarks)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (cid, old_status, status, admin_id, timestamp, remarks or None),
                )
            if assignment_changed:
                note = f"Assigned to {assignee_name}" if new_assignee is not None else "Unassigned"
                conn.execute(
                    """INSERT INTO complaint_updates
                       (complaint_id, old_status, new_status, updated_by, update_time, remarks)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (cid, status, status, admin_id, timestamp, note),
                )
    return get_complaint_admin(cid)


# ---------- Delete ----------

def delete_complaint(complaint_id):
    """Permanently delete a complaint (its history is deleted too, via ON DELETE CASCADE).

    The web app only allows this for logged-in administrators.
    """
    cid = normalise_complaint_id(complaint_id)
    if cid is None:
        raise NotFoundError("No complaint found with that ID.")
    with closing(database.get_connection()) as conn:
        with conn:
            cursor = conn.execute("DELETE FROM complaints WHERE complaint_id = ?", (cid,))
    if cursor.rowcount == 0:
        raise NotFoundError("No complaint found with that ID.")
