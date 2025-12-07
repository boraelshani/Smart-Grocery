#!/usr/bin/env python3
"""Test script to verify BILLA products API returns correct data."""

import sys
import json
from urllib.request import urlopen

try:
    # Fetch BILLA products
    with urlopen('http://localhost:5001/api/store/BILLA/products') as response:
        data = json.loads(response.read().decode())
    
    print(f"✓ API Response received")
    print(f"✓ Total BILLA products: {data.get('count', 0)}\n")
    
    if data.get('count', 0) == 0:
        print("✗ No products found for BILLA")
        sys.exit(1)
    
    print("First 5 BILLA products:\n")
    for i, product in enumerate(data.get('products', [])[:5], 1):
        name = product.get('name', 'Unknown')
        price = product.get('price', 'N/A')
        category = product.get('category', 'N/A')
        
        print(f"{i}. {name}")
        print(f"   Price: €{price}")
        print(f"   Category: {category}")
        
        # Check matched_stores for BILLA-specific data
        matched = product.get('matched_stores', [])
        if matched:
            store_data = matched[0]
            store_name = store_data.get('store', 'N/A')
            store_price = store_data.get('price', 'N/A')
            store_image = store_data.get('image', 'N/A')
            
            print(f"   ✓ Matched Store: {store_name}")
            print(f"   ✓ Store Price: €{store_price}")
            if store_image != 'N/A':
                print(f"   ✓ Store Image: {store_image[:70]}...")
            else:
                print(f"   ✗ No store-specific image")
        else:
            print(f"   ✗ No matched_stores data")
        print()
    
    print("\n✓ BILLA API test completed successfully!")
    
except Exception as e:
    print(f"✗ Error: {e}")
    sys.exit(1)
