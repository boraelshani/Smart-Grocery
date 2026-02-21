
import sys
import os
import traceback

# Ensure we're in the right directory
sys.path.append(os.getcwd())

try:
    from app import app
except Exception as e:
    print(f"Error importing app: {e}")
    traceback.print_exc()
    sys.exit(1)

client = app.test_client()

def check_route(route):
    print(f"\n--- Checking {route} ---")
    try:
        # Mock session if needed
        with client.session_transaction() as sess:
            sess['user'] = 'test@example.com' 

        response = client.get(route, follow_redirects=True)
        print(f"Status Code: {response.status_code}")
        if response.status_code != 200:
            print("Response Data (Truncated):")
            print(response.data.decode('utf-8')[:500])
    except Exception as e:
        print(f"EXCEPTION: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    check_route('/shopping-list')
    check_route('/featured-deals')
    check_route('/stores')
