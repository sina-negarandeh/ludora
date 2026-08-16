from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

print("Testing /api/games...")
response = client.get("/api/games?limit=1")
print(response.status_code)

print("Testing /api/categories...")
response = client.get("/api/categories?limit=1")
print(response.status_code)

print("Testing /api/games/174430...")
response = client.get("/api/games/174430")
print(response.status_code)

print("Testing /api/games/174430/reviews...")
response = client.get("/api/games/174430/reviews")
print(response.status_code)

print("Testing /api/games/174430/aspects...")
response = client.get("/api/games/174430/aspects")
print(response.status_code)

print("Testing /api/games/174430/recommendations...")
response = client.get("/api/games/174430/recommendations")
print(response.status_code)

print("Testing /api/recommendation-models...")
response = client.get("/api/recommendation-models")
print(response.status_code)
