from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.errors import AppError, NotFoundError


def test_app_error_returns_consistent_shape():
    app = FastAPI()

    from app.main import app_error_handler

    app.add_exception_handler(AppError, app_error_handler)

    @app.get("/boom")
    def boom():
        raise NotFoundError("Widget not found", details={"widget_id": "42"})

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/boom")
    assert response.status_code == 404
    assert response.json() == {
        "code": "not_found",
        "message": "Widget not found",
        "details": {"widget_id": "42"},
    }
