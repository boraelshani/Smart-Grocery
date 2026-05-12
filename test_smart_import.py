#!/usr/bin/env python3
"""
Test script for Smart Import AI feature
"""
import json
from scripts.ai_product_fetcher import fetch_product_from_url

# Test URLs
test_urls = [
    {
        "name": "Hofer - BBQ Grillschalen",
        "url": "https://www.hofer.at/de/p.bbq-grillschalen-eckig--teilig.000000000000478567.html",
        "expected": {
            "name_contains": "BBQ Grillschalen",
            "name_not_contains": "Meine HOFER Produktempfehlung",
            "price_range": (1.0, 2.5),
            "has_offer": True
        }
    },
    {
        "name": "Hofer - FAIR HOF Grill-Burger",
        "url": "https://www.hofer.at/de/p.fair-hof-grill-burger.000000000000736117.html",
        "expected": {
            "name_contains": "FAIR HOF",
            "name_not_contains": "Meine HOFER",
            "price_range": (1.5, 2.5),
            "has_size": True
        }
    }
]

def test_product(test_case):
    """Test a single product URL"""
    print(f"\n{'='*70}")
    print(f"Testing: {test_case['name']}")
    print(f"URL: {test_case['url']}")
    print(f"{'='*70}")
    
    result = fetch_product_from_url(test_case['url'])
    
    if not result.get('success'):
        print(f"❌ FAILED: {result.get('error', 'Unknown error')}")
        return False
    
    data = result['data']
    expected = test_case['expected']
    passed = True
    
    # Test name
    name = data.get('name_de', '')
    if 'name_contains' in expected:
        if expected['name_contains'] in name:
            print(f"✅ Name contains '{expected['name_contains']}': {name}")
        else:
            print(f"❌ Name should contain '{expected['name_contains']}': {name}")
            passed = False
    
    if 'name_not_contains' in expected:
        if expected['name_not_contains'] not in name:
            print(f"✅ Name doesn't contain '{expected['name_not_contains']}'")
        else:
            print(f"❌ Name should NOT contain '{expected['name_not_contains']}': {name}")
            passed = False
    
    # Test price
    if 'price_range' in expected:
        try:
            price = float(data.get('price', 0))
            min_price, max_price = expected['price_range']
            if min_price <= price <= max_price:
                print(f"✅ Price in range €{min_price}-€{max_price}: €{price}")
            else:
                print(f"❌ Price €{price} not in expected range €{min_price}-€{max_price}")
                passed = False
        except:
            print(f"❌ Invalid price: {data.get('price')}")
            passed = False
    
    # Test offer details
    if expected.get('has_offer'):
        if data.get('offer_details'):
            print(f"✅ Has offer details: {data.get('offer_details')}")
        else:
            print(f"⚠️  No offer details found (expected)")
    
    # Test size
    if expected.get('has_size'):
        if data.get('size'):
            print(f"✅ Has size: {data.get('size')}")
        else:
            print(f"⚠️  No size found (expected)")
    
    # Show all extracted data
    print(f"\n📦 Extracted Data:")
    print(f"   Name (DE): {data.get('name_de')}")
    print(f"   Name (EN): {data.get('name_en')}")
    print(f"   Brand: {data.get('brand_raw')}")
    print(f"   Price: €{data.get('price')}")
    print(f"   Promo Price: €{data.get('promo_price')}" if data.get('promo_price') else "   Promo Price: None")
    print(f"   Size: {data.get('size')}")
    print(f"   Unit Price: {data.get('unit_price')}")
    print(f"   Offer Details: {data.get('offer_details')}")
    print(f"   Category: {data.get('category_path')}")
    
    return passed

if __name__ == '__main__':
    print("🧪 Smart Import AI Feature - Test Suite")
    print("="*70)
    
    total = len(test_urls)
    passed = 0
    
    for test_case in test_urls:
        if test_product(test_case):
            passed += 1
    
    print(f"\n{'='*70}")
    print(f"📊 Test Results: {passed}/{total} passed")
    print(f"{'='*70}")
    
    if passed == total:
        print("✅ All tests passed!")
        exit(0)
    else:
        print(f"❌ {total - passed} test(s) failed")
        exit(1)
