"""
═══════════════════════════════════════════════════════════════════════════
CHECK USER SCRIPT - Debugging Utility
═══════════════════════════════════════════════════════════════════════════
Purpose: 
Quickly diagnose user account issues in production or dev.

Usage: 
Run via terminal: `python scripts/check_user.py`

Logic:
- Connects to the database using the shared `get_db` utility.
- Queries for a specific hardcoded email ('user1@example.com').
- Prints the raw JSON record to stdout for inspection.
═══════════════════════════════════════════════════════════════════════════
"""
import sys
import os
import json
from dotenv import load_dotenv

# 1. SETUP PATH
# We need to import 'utils' which is in the parent directory.
# This adds the current working directory to the Python path.
sys.path.append(os.getcwd())

from utils.db import get_db

# 2. LOAD CONFIG
# Ensures environment variables (MONGO_URI) are available
load_dotenv()

# 3. EXECUTE CHECK
# Establish connection
db = get_db()

if db is not None:
    # Query for the test user
    target_email = 'user1@example.com'
    print(f"--- Searching for {target_email} ---")
    
    user = db.users.find_one({'email': target_email})
    
    if user:
        # Success: Dump the record formatted nicely
        # default=str handles ObjectId and datetime serialization automatically
        print(f"Found User Record:")
        print(json.dumps(user, indent=4, default=str))
    else:
        print("User not found in database.")
else:
    print("FATAL: Could not connect to database. Check MONGO_URI.")

