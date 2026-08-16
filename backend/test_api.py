import urllib.request
import json

try:
    req = urllib.request.Request("http://127.0.0.1:8000/api/games?limit=2")
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode())
        print(f"Games returned: {len(data.get('items', []))}")
        print(f"Total: {data.get('total')}")
except Exception as e:
    print(f"Error: {e}")
