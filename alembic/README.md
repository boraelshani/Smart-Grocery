Alembic scaffold

This folder contains a minimal Alembic environment and a revision that creates
the index tweaks recommended by `models/postgres_models.py`.

To use:

1. Install Alembic in your venv:

```bash
./venv/bin/python -m pip install alembic
```

2. Set `DATABASE_URL` in your environment (or edit `alembic.ini`):

```bash
export DATABASE_URL=postgres://user:pass@host:5432/dbname
```

3. Run the upgrade:

```bash
./venv/bin/alembic -c alembic.ini upgrade head
```

Or run individual revision by filename.

This scaffold is intentionally minimal — if you already use Flask-Migrate/Alembic,
integrate the `alembic/versions/0001_add_indexes.py` content into your migration workflow.
