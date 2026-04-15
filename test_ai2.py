import requests
import json

api_key = "AIzaSyAsBWK5QeCX29drZHf5pfCh1aeynXRinn0"
url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"

try:
    r = requests.get(url)
    print("STATUS:", r.status_code)
    try:
        print("JSON:", json.dumps(r.json(), indent=2)[:2000])
    except Exception:
        print("RAW:", r.text[:500])
except Exception as e:
    print("ERROR:", e)
