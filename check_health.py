import requests

try:
    response = requests.get('http://localhost:1551/health')
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print("Health Response:")
        for key, value in data.items():
            print(f"  {key}: {value}")
    else:
        print(f"Error Response: {response.text}")
except Exception as e:
    print(f"Connection error: {e}") 