from models.notifications_model import notifications_model
import sys
import os

print("Starting cleanup of old notifications...")
print(f"MONGO_URI from env: {os.getenv('MONGO_URI')}")
try:
    # Debug info
    if hasattr(notifications_model, 'db'):
        print(f"Connected to DB: {notifications_model.db.name}")
        count_all = notifications_model.db.notifications.count_documents({})
        print(f"Total notifications available: {count_all}")
    else:
        print("Model has no DB connection!")

    count = notifications_model.cleanup_old_notifications(7)
    print(f"Successfully deleted {count} notifications older than 7 days.")
except Exception as e:
    print(f"Error during cleanup: {e}")

print("Cleanup complete.")
