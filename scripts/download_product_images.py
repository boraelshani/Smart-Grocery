import os
import requests
import re
import time
import glob
from bs4 import BeautifulSoup
from app import app
from models.postgres_models import db, Product, Offer
import logging

import sys
import argparse
from sqlalchemy.exc import OperationalError, PendingRollbackError

# Configure logging
logging.basicConfig(
    filename='image_download.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
logging.getLogger('').addHandler(console)

def extract_image_url(page_url):
    """
    Attempt to extract the main image URL from a store product page.
    Currently optimized for Billa (shop.billa.at)
    Returns: (image_url, status_code)
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        }
        res = requests.get(page_url, headers=headers, timeout=10)
        
        # We handle 404s specially now
        if res.status_code == 404:
            return None, 404
            
        res.raise_for_status()
        
        # Method 1: Check for og:image meta tag
        soup = BeautifulSoup(res.text, 'html.parser')
        og_image = soup.find('meta', property='og:image')
        if og_image and og_image.get('content') and 'logo' not in og_image['content'].lower():
            return og_image['content'], res.status_code
            
        # Method 2: Regex for Billa media assets if og:image fails
        # Finds URLs like: https://media.billa.at/articles/... 
        m = re.search(r'(https://media\.billa\.at/articles/[^"\'\\]+)', res.text)
        if m:
            return m.group(1), res.status_code
            
        return None, res.status_code
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response else None
        logging.error(f"HTTP Error for {page_url}: {str(e)}")
        return None, status
    except Exception as e:
        logging.error(f"Failed to fetch or parse {page_url}: {str(e)}")
        return None, None

def download_image(url, local_path):
    """Download the image to the local path."""
    try:
        res = requests.get(url, stream=True, timeout=10)
        res.raise_for_status()
        with open(local_path, 'wb') as f:
            for chunk in res.iter_content(chunk_size=8192):
                f.write(chunk)
        return True
    except Exception as e:
        logging.error(f"Failed to download image from {url}: {str(e)}")
        return False

def run_sync(resume_id=None, target_store_id=None):
    with app.app_context():
        # Setup local directory
        images_dir = os.path.join(app.root_path, 'static', 'products', 'images')
        os.makedirs(images_dir, exist_ok=True)
        
        logging.info(f"Starting image download sync... {'Resuming from ID: ' + str(resume_id) if resume_id else ''}")
        if target_store_id:
            logging.info(f"Filtering ONLY for Store ID: {target_store_id}")
        
        success_count = 0
        failure_count = 0
        
        # Batch processing strategy to prevent dropping connections
        batch_size = 100
        last_id = resume_id or 0
        
        while True:
            try:
                # Build product query
                query = Product.query.filter(
                    Product.id >= last_id,
                    db.or_(
                        Product.default_image_url.is_(None),
                        ~Product.default_image_url.like('/static/products/images/%')
                    )
                )
                
                if target_store_id:
                    query = query.join(Offer).filter(Offer.store_id == str(target_store_id))
                
                products = query.order_by(Product.id.asc()).limit(batch_size).all()
                
                if not products:
                    break
                    
                for product in products:
                    last_id = product.id + 1
                    
                    # Prevent re-downloading
                    existing_files = glob.glob(os.path.join(images_dir, f"prod_{product.id}.*"))
                    if existing_files:
                        continue

                    # Get offer URL
                    offer_query = Offer.query.filter(
                        Offer.product_id == product.id, 
                        Offer.product_url.isnot(None),
                        ~Offer.product_url.like('%/search?q=%')
                    )
                    if target_store_id:
                        offer_query = offer_query.filter(Offer.store_id == str(target_store_id))
                        
                    offer = offer_query.order_by(Offer.updated_at.desc()).first()
                    
                    if not offer or not offer.product_url:
                        continue
                        
                    logging.info(f"Processing Product ID: {product.id} - URL: {offer.product_url}")
                    
                    # Fetch
                    image_url, status_code = extract_image_url(offer.product_url)
                    time.sleep(1)
                    
                    if status_code == 404:
                        logging.info(f"Product ID: {product.id} returned 404. Archiving offer.")
                        # Archive logic
                        for opt_offer in Offer.query.filter_by(product_id=product.id).all():
                            opt_offer.is_available = False
                        db.session.commit()
                        continue
                        
                    if not image_url:
                        logging.warning(f"Product ID: {product.id} - Could not find image URL on page.")
                        failure_count += 1
                        continue
                        
                    ext = 'jpg'
                    if 'png' in image_url.lower(): ext = 'png'
                    elif 'webp' in image_url.lower(): ext = 'webp'
                    
                    filename = f"prod_{product.id}.{ext}"
                    local_path = os.path.join(images_dir, filename)
                    relative_url = f"/static/products/images/{filename}"
                    
                    if download_image(image_url, local_path):
                        product.default_image_url = relative_url
                        db.session.commit()
                        logging.info(f"Success! Updated Product {product.id} with image {relative_url}")
                        success_count += 1
                    else:
                        failure_count += 1
                        
            except (OperationalError, PendingRollbackError) as e:
                db.session.remove()
                logging.error(f"Database connection error, retrying from last_id {last_id} after 5 seconds: {str(e)}")
                time.sleep(5)
                try:
                    db.engine.dispose()
                except:
                    pass
                continue
            except Exception as e:
                db.session.remove()
                logging.error(f"Unexpected loop exception: {str(e)}")
                failure_count += 1
                last_id += 1 # Skip failing id
                continue
                
        logging.info(f"Completed! Successes: {success_count}, Failures: {failure_count}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--resume', type=int, help='Start processing from a specific Product ID', default=0)
    parser.add_argument('--store-id', type=str, help='Filter processing specifically by a Store ID (e.g. "spar")', default=None)
    args = parser.parse_args()
    
    run_sync(resume_id=args.resume, target_store_id=args.store_id)