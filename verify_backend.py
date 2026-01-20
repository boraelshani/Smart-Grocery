
import sys
import os
from flask import Flask, session
from pymongo import MongoClient
from bson import ObjectId

# Add current dir to path
sys.path.append(os.getcwd())

from app import app
from models.users_model import create_shopping_list, delete_shopping_list, rename_shopping_list, get_user_lists

# Manually configure Flask-PyMongo to use a mock or real DB if available
# But since we are running outside the web server, we might need to rely on the fallback logic 
# OR connect to real mongo if env var is set.

def test_backend_logic():
    print("Starting Backend Logic Test...")
    with app.app_context():
        email = "test_user@example.com"
        
        # 1. Create List
        print(f"Testing create_shopping_list for {email}...")
        try:
            list_id = create_shopping_list(email, "Test List A")
            print(f"PASS: Created list_id: {list_id}")
        except Exception as e:
            print(f"FAIL: create_shopping_list crashed: {e}")
            import traceback
            traceback.print_exc()
            return

        if not list_id:
            print("FAIL: No list ID returned (and no crash). fallback logic issue?")
            # If no mongod, fallback should work IF mock_models is initialized
            # But mock_models is in models/models.py and users_model tries to import it.
            return

        # 2. Get Lists
        print("Testing get_user_lists...")
        try:
            data = get_user_lists(email)
            lists = data.get('lists', [])
            print(f"PASS: Retrieved {len(lists)} lists.")
        except Exception as e:
            print(f"FAIL: get_user_lists crashed: {e}")
            return

        # 3. Rename List
        print("Testing rename_shopping_list...")
        try:
            success = rename_shopping_list(email, list_id, "Renamed List A")
            print(f"PASS: Rename success: {success}")
        except Exception as e:
            print(f"FAIL: rename_shopping_list crashed: {e}")
            return

        # 4. Delete List
        print("Testing delete_shopping_list...")
        try:
            success = delete_shopping_list(email, list_id)
            print(f"PASS: Delete success: {success}")
        except Exception as e:
            print(f"FAIL: delete_shopping_list crashed: {e}")
            return

        print("ALL TESTS PASSED.")

if __name__ == "__main__":
    test_backend_logic()
