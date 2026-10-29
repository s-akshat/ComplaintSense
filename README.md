# ComplainSense

**Smart complaint prioritisation based on urgency and severity.**

People submit complaints (electricity, water, internet, security, ...) and rate how *urgent* and how *severe*
each one is (1-5). ComplainSense calculates a priority score, ranks all complaints, and shows administrators
what to handle first.

> Educational decision-support tool, **not** a validated safety assessment. Scores come from self-reported
> ratings. Complaints in emergency categories (Security, Fire Safety, Medical, Electrical Hazard) are always
> flagged for immediate human review, whatever their score.

## Tech stack

| Part | Technology |
|---|---|
| Backend / logic | Python 3 + Flask |
| Database | SQLite (one file, nothing to install) |
| Frontend | HTML, CSS, vanilla JavaScript |
| Analysis / charts | Pandas, Matplotlib |
| Tests | pytest |

## Quick start (Windows 11)

1. Install Python from https://www.python.org/downloads/ and tick **"Add python.exe to PATH"** on the first installer screen.
2. Unzip this folder. Double-click **`setup.bat`** (one time; needs internet; takes a few minutes).
   It creates a private environment, installs the libraries, creates the database + sample data, and runs the tests.
3. Double-click **`run.bat`**. Your browser opens ComplainSense at http://127.0.0.1:5000.
4. Admin login: username `admin`, password in the file **`ADMIN_LOGIN.txt`** (created by setup).

To stop the app, close the black `run.bat` window.

### Manual commands (PowerShell, inside the project folder)

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python seed.py --sample        # database + admin + SAMPLE data
python -m pytest -v            # run the tests
python app.py                  # start the site
```

Choose your own admin password: `python seed.py --admin-password YourPassword123`

## Priority algorithm

`score = urgency x 0.5 + severity x 0.5` (urgency and severity are whole numbers 1-5)

| Score | Level |
|---|---|
| 4.0 - 5.0 | CRITICAL |
| 3.0 - 3.5 | HIGH |
| 2.0 - 2.5 | MEDIUM |
| 1.0 - 1.5 | LOW |

Sorting: highest score first; equal scores -> oldest complaint first.

## Files

| File | Purpose |
|---|---|
| `app.py` | Flask server: pages, API routes, login, error handling |
| `priority.py` | Score, level, emergency flag, sorting |
| `complaints.py` | Validation, ID generation, create / read / update / delete, history |
| `auth.py` | Users, password hashing, login checks |
| `database.py` | SQLite connection and table definitions |
| `analytics.py` | Pandas statistics and Matplotlib charts |
| `seed.py` | First-time setup, admin account, SAMPLE data |
| `templates/`, `static/` | HTML pages, CSS, JavaScript |
| `tests/` | Automated tests |
| `setup.bat`, `run.bat` | One-click install and start (Windows) |

How they connect: browser JavaScript calls `/api/...` in `app.py` -> `app.py` calls `complaints.py`,
`auth.py` or `analytics.py` -> those use `priority.py` and `database.py` -> SQLite file `complainsense.db`.

## Database

- `users(user_id PK, name, email_or_username UNIQUE, password_hash, role)`
- `complaints(complaint_id PK, user_id FK, complainant_name, contact, category, description, location, urgency, severity, priority_score, priority_level, needs_immediate_review, status, created_at, updated_at, assigned_to FK)`
- `complaint_updates(update_id PK, complaint_id FK, old_status, new_status, updated_by FK, update_time, remarks)`

One complaint has many updates (deleting a complaint deletes its history). All SQL uses parameterised queries.

## Security notes

- Passwords are stored only as salted hashes (PBKDF2-SHA256).
- Admin pages and API routes require an admin login; student-role accounts are refused.
- 5 failed logins lock that username for one minute.
- Page content is built with `textContent`, so typed text cannot run as script.
- The public tracking page shows only status, priority and dates, never names or contact details.
- `.env`, `.secret_key`, `ADMIN_LOGIN.txt` and `*.db` are in `.gitignore`. Never commit them.

## Testing

Run `python -m pytest -v`. The suite covers score maths and every level boundary, invalid ratings, bad or
empty descriptions, ID format/uniqueness, insert/retrieve, status updates and history, sorting and filtering,
unknown IDs, login and admin permissions, SQL-injection-style input, charts, and data persisting after a
restart. Each test uses its own temporary database, so your real data is never touched.

Sample data from `seed.py --sample` is made-up demo data. It is not testing evidence.

## Known limitations

- Runs locally (Flask development server). A public deployment would need a production server, HTTPS and a stronger rate limiter.
- Priority depends on self-reported ratings.
- Only one admin account is created by default; there is no screen for managing users.
- No email or SMS notifications.

## Future enhancements

Email notifications, CSV export, user accounts for students, an admin screen for managing users,
and (optionally) a machine-learning model to suggest ratings from the description text.
