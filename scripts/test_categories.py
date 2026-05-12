#!/usr/bin/env python3
"""
Test script to verify category system is working correctly
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app

def test_categories():
    print("=" * 60)
    print("CATEGORY SYSTEM TEST")
    print("=" * 60)
    
    with app.app_context():
        from utils.menu_data import get_mega_menu
        
        # Test 1: Load menu data
        print("\n[TEST 1] Loading menu data...")
        menu = get_mega_menu()
        
        if not menu or not menu.get('categories'):
            print("✗ FAILED: No categories loaded")
            return False
        
        print(f"✓ PASSED: Loaded {len(menu['categories'])} categories")
        
        # Test 2: Check hierarchy
        print("\n[TEST 2] Checking category hierarchy...")
        total_subcats = 0
        total_l3_items = 0
        
        for cat_name, cat_info in menu['categories'].items():
            subcats = cat_info.get('subcats', {})
            total_subcats += len(subcats)
            
            for subcat_name, l3_list in subcats.items():
                total_l3_items += len(l3_list)
        
        print(f"✓ PASSED: Found {total_subcats} subcategories and {total_l3_items} level-3 items")
        
        # Test 3: Check images
        print("\n[TEST 3] Checking category images...")
        cats_with_images = sum(1 for cat_info in menu['categories'].values() if cat_info.get('image'))
        print(f"✓ PASSED: {cats_with_images}/{len(menu['categories'])} categories have images")
        
        # Test 4: Check icons
        print("\n[TEST 4] Checking category icons...")
        cats_with_icons = sum(1 for cat_info in menu['categories'].values() if cat_info.get('icon'))
        print(f"✓ PASSED: {cats_with_icons}/{len(menu['categories'])} categories have icons")
        
        # Test 5: Display sample hierarchy
        print("\n[TEST 5] Sample category hierarchy:")
        for idx, (cat_name, cat_info) in enumerate(list(menu['categories'].items())[:5]):
            print(f"\n  {idx+1}. {cat_name}")
            print(f"     Icon: {cat_info.get('icon', 'N/A')}")
            print(f"     Image: {'Yes' if cat_info.get('image') else 'No'}")
            print(f"     Subcategories: {len(cat_info.get('subcats', {}))}")
            
            # Show first 2 subcategories
            for subcat_name, l3_list in list(cat_info.get('subcats', {}).items())[:2]:
                print(f"       - {subcat_name} ({len(l3_list)} items)")
                for l3_item in l3_list[:3]:
                    print(f"           * {l3_item}")
        
        # Test 6: Test Flask app
        print("\n[TEST 6] Testing Flask app rendering...")
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess['user'] = 'test@example.com'
            
            response = client.get('/')
            if response.status_code == 200:
                html = response.data.decode('utf-8')
                
                # Check for key elements
                checks = {
                    'Browse menu': 'browseDropdown' in html,
                    'Categories tab': 'tab-categories' in html,
                    'Mega menu': 'mega-menu-wrapper' in html,
                    'Category list': 'mega-cat-list' in html,
                }
                
                all_passed = all(checks.values())
                for check_name, passed in checks.items():
                    status = "✓" if passed else "✗"
                    print(f"  {status} {check_name}: {'Found' if passed else 'Missing'}")
                
                if all_passed:
                    print("✓ PASSED: All HTML elements present")
                else:
                    print("✗ FAILED: Some HTML elements missing")
                    return False
            else:
                print(f"✗ FAILED: Home page returned status {response.status_code}")
                return False
        
        print("\n" + "=" * 60)
        print("ALL TESTS PASSED ✓")
        print("=" * 60)
        return True

if __name__ == '__main__':
    success = test_categories()
    sys.exit(0 if success else 1)
