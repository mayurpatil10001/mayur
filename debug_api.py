from fastapi.testclient import TestClient
from trading_platform.api.main import create_app

app = create_app()
client = TestClient(app)

response = client.get('/health')
print('Status:', response.status_code)
print('Content:', response.text)
print('Headers:', dict(response.headers))