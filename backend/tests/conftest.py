import os
import tempfile
from pathlib import Path

# Set database BEFORE importing app.db (engine created at import time).
_path = Path(tempfile.gettempdir()) / f'elite_test_{os.getpid()}.sqlite3'
os.environ['DATABASE_URL'] = f'sqlite:///{_path}'
os.environ['JWT_SECRET'] = 'local-tests-jwt-secret-at-least-32-characters'
os.environ['AUDIT_SECRET'] = 'local-tests-audit-secret-at-least-32-characters'
os.environ['DEMO_PASSWORD'] = 'Demo@2026'
os.environ['ENVIRONMENT'] = 'test'

import pytest
from fastapi.testclient import TestClient
from app.db import Base, engine, SessionLocal
from app.main import app
from app.seed import seed


@pytest.fixture
def client():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed(db)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def auth(client):
    def _auth(email='ana@demo.com'):
        response = client.post('/api/auth/login', json={'email': email, 'password': 'Demo@2026'})
        assert response.status_code == 200, response.text
        return {'Authorization': f"Bearer {response.json()['access_token']}"}
    return _auth
