**Database migrations (manual instructions)**

This folder contains safe, idempotent SQL migration helpers that can be applied
to your PostgreSQL database. They are not executed automatically by the app.

How to apply (example using `psql`):

1. Export your database URL:

```
export DATABASE_URL=postgres://user:pass@host:5432/dbname
```

2. Apply the migration file:

```
psql "$DATABASE_URL" -f migrations/add_indexes.sql
```

Or connect via your preferred DB client and run the script contents.

Notes:
- `CREATE INDEX IF NOT EXISTS` is used so re-running is safe.
- If you use Alembic/Flask-Migrate, convert this SQL into an Alembic revision.
