# AI Coding Agent Instructions for Smart-Grocery

## Project Overview
A Flask-based price comparison web application using MongoDB. Organized by Blueprints (routes/), Models (models/), and Utilities (utils/).

## Core Architecture Patterns
- **Database Access**: Always use the `mongo` instance from `utils.db` or the `get_db()` helper in `routes/main_routes.py`.
  - Production: `flask_pymongo`.
  - Local/Fallback: Direct `MongoClient` or in-memory mocks in `models/models.py`.
- **Routing**: Routes are split across `routes/main_routes.py`, `routes/auth_routes.py`, and `routes/admin_routes.py`. Use the respective Blueprints (`main_bp`, `auth_bp`, `admin_bp`).
- **Data Handling**:
  - Convert `ObjectId` and `Decimal128` to serializable types before returning JSON using `sanitize_mongo_doc`.
  - Use `bcrypt` for password hashing/verification (see `models/users_model.py`).

## Key Workflows
- **Running the App**: Execute `python app.py`. It automatically detects and re-executes using `./venv/bin/python` if available.
- **Environment**: Define `MONGO_URI`, `SECRET_KEY`, and `JWT_SECRET_KEY` in a `.env` file.
- **Data Migrations**: Use scripts in `scripts/` (e.g., `import_featured_deals.py`) for manual data updates.

## Coding Conventions
- **Fallback Logic**: Maintain high availability by providing fallback data (JSON files in `data/` or mocks in `models/models.py`) when MongoDB is unavailable.
- **Sessions**: The current user's email is stored in `session['user']`. Use `_get_user_email()` in routes for a consistent way to retrieve it.
- **Frontend**: 
  - CSS is centralized in `static/style.css`.
  - JavaScript logic is in `static/js/script.js`.
  - Templates use Jinja2 and Bootstrap 5.

## Reference Files
- `app.py`: Main entry point and Flask configuration.
- `utils/db.py`: MongoDB initialization.
- `routes/main_routes.py`: Core logic for product comparison and shopping lists.
- `models/users_model.py`: User CRUD and authentication logic.
