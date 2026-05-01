import requests

print("Program started")

response = requests.get("https://api.github.com")

print("Status Code:", response.status_code)
print("Response Length:", len(response.text))