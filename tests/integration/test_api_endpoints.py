"""
tests/integration/test_api_endpoints.py
=========================================
Integration tests for FastAPI endpoints: health, trades, analytics, recommendations, ingestion.
"""

import pytest
from fastapi.testclient import TestClient
from backend.api.app import create_app

app = create_app()
client = TestClient(app)


def test_health_check_endpoint():
    """Verify /health returns 200 OK."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "version" in data


def test_trades_endpoint():
    """Verify /api/v1/trades returns 200 OK paginated structure."""
    response = client.get("/api/v1/trades")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data


def test_analytics_summary_endpoint():
    """Verify /api/v1/analytics/summary returns performance snapshot."""
    response = client.get("/api/v1/analytics/summary")
    assert response.status_code == 200
    data = response.json()
    assert "net_pnl" in data
    assert "trade_count" in data


def test_recommendations_endpoint():
    """Verify /api/v1/recommendations returns list."""
    response = client.get("/api/v1/recommendations")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_invalid_trade_id():
    """Verify non-existent trade returns 404."""
    response = client.get("/api/v1/trades/nonexistent-id-12345")
    assert response.status_code == 404
