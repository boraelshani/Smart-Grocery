"""
Import featured deals from JSON file to MongoDB
"""
import json
import sys
import os
from dotenv import load_dotenv

# Add project root to path to allow imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.db import get_db

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
        db = get_db()
        if not db:
            print("Error: Could not connect to database")
            return
        
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

            # Add broadcast notifications for the new deals
            print("Sending broadcast notifications for new deals...")
            try:
                # Add project root to sys.path to import models
                sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
                # Ensure Env is loaded for Models
                if not os.environ.get('MONGO_URI'):
                   from dotenv import load_dotenv
                   load_dotenv()
                   
                from models.notifications_model import NotificationsModel
                nm = NotificationsModel()
                
                # Notify users about the top 3-5 most exciting deals (e.g. highest discount)
                # Ensure we have the full deal objects with IDs
                # We need to re-fetch the inserted deals to get their generated _ids if they weren't provided
                
                inserted_deals = list(db.featured_deals.find().sort('created_at', -1).limit(5))
                count = 0
                
                for deal in inserted_deals:
                     # Calculate discount label if missing
                    discount_label = deal.get('discount_label')
                    if not discount_label and deal.get('offer'):
                         discount_label = deal.get('offer')
                    if not discount_label and deal.get('original_price') and deal.get('price'):
                         try:
                             pct = int((1 - (deal['price'] / deal['original_price'])) * 100)
                             discount_label = f"{pct}% OFF"
                         except:
                             discount_label = "Great Deal"

                    # Create rich notification data
                    notification_data = {
                        'type': 'deal_alert',
                        'title': f"New Deal: {deal.get('title')}",
                        'message': f"Don't miss out! {deal.get('description', 'Check out this amazing offer.')}",
                        'priority': 'high',
                        'deal_id': str(deal['_id']), # CRITICAL for Rich Card
                        # Pass these to be redundant/safe but deal_id lookup will handle most
                        'product_name': deal.get('title'),
                        'store_name': deal.get('store'),
                        'offer_name': discount_label,
                        'product_image': deal.get('image'),
                        'price': deal.get('price'),
                        'old_price': deal.get('original_price')
                    }
                    
                    nm.broadcast_notification(notification_data)
                    count += 1
                    print(f"Sent notification for deal: {deal.get('title')}")

                print(f"Broadcasted {count} specific deal alerts.")
            except Exception as e:
                print(f"Could not send broadcast: {e}")
                import traceback
                traceback.print_exc()
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
