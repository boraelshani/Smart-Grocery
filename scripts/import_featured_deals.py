"""
Import featured deals from JSON file to MongoDB
"""
import json
import sys
import os
from pymongo import MongoClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def import_featured_deals():
    """Import featured deals from JSON file to MongoDB"""
    
    # Read the JSON file
    json_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'featured_deals.json')
    
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            deals = json.load(f)
        
        print(f"Loaded {len(deals)} featured deals from JSON file")
        
        # Connect to MongoDB
        mongo_uri = os.getenv('MONGO_URI')
        if not mongo_uri:
            print("Error: MONGO_URI not found in environment variables")
            return
        
        client = MongoClient(mongo_uri)
        db = client.get_database()  # Use default database from URI
        
        # Clear existing featured deals
        result = db.featured_deals.delete_many({})
        print(f"Deleted {result.deleted_count} existing featured deals from MongoDB")
        
        # Insert new featured deals
        if deals:
            # Remove the temporary 'id' field if it exists (MongoDB will create _id)
            for deal in deals:
                if 'id' in deal and deal['id'].startswith('fd_'):
                    del deal['id']
            
            result = db.featured_deals.insert_many(deals)
            print(f"Inserted {len(result.inserted_ids)} featured deals into MongoDB")
            print("Featured deals successfully imported!")
        else:
            print("No deals to import")
            
    except FileNotFoundError:
        print(f"Error: Could not find file {json_path}")
    except Exception as e:
        print(f"Error importing featured deals: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    import_featured_deals()
