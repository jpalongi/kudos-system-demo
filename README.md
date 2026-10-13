# Kudos

A small Flask and SQLite demo where signed-in employees can thank a colleague. It includes a recent feed and an admin page for hiding, restoring or removing messages.

## Run it locally

Use Python 3.10 or later. From this folder:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open <http://127.0.0.1:5000>. The local demo lets you choose a sample account:

- Alex Morgan, Sam Taylor and Jamie Chen are employee accounts.
- Morgan Admin is the administrator account.

The app stores its local database in `instance/kudos.sqlite` and creates it on first run.

## Run tests

```bash
python -m unittest -v
```

## Important

The account picker is only for a local demonstration. Before using this in a real employee portal, replace it with the organisation’s sign-in system, set a secret `KUDOS_SECRET_KEY`, use a production database, and review the moderation and data-retention rules. The app refuses to start in production mode if demo sign-in is still enabled or the secret key is missing.
