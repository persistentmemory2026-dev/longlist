from fastapi.testclient import TestClient

import job_store
from main import app


def test_health():
    job_store.init_db()
    with TestClient(app) as client:
        r = client.get("/")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert "jobs_persisted" in data
