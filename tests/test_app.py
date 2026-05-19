from io import BytesIO
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from src.app import app

def _make_jpeg_bytes() -> bytes:
    img = Image.new("RGB", (10, 10), color=(255, 0, 0))
    buf = BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()

@pytest.fixture()
def client():
    with patch("src.app.VQAEngine") as mock_engine_cls:
        mock_engine = MagicMock()
        mock_engine.predict.return_value = "ok"
        mock_engine_cls.return_value = mock_engine

        # Ensure lazy engine is re-created under patch
        import src.app as app_module
        app_module._engine = None

        with TestClient(app) as c:
            yield c

def test_predict_success(client):
    data = {
        "question": "What is this?",
        "image": ("x.jpg", BytesIO(_make_jpeg_bytes()), "image/jpeg"),
    }
    resp = client.post("/predict", data=data)
    assert resp.status_code == 200
    assert resp.json()["answer"] == "ok"

def test_predict_missing_image(client):
    # FastAPI will return 422 Unprocessable Entity for missing required fields
    resp = client.post(
        "/predict", data={"question": "Hi"}, content_type="multipart/form-data"
    )
    assert resp.status_code == 422

def test_predict_missing_question(client):
    data = {"image": ("x.jpg", BytesIO(_make_jpeg_bytes()), "image/jpeg")}
    resp = client.post("/predict", data=data, content_type="multipart/form-data")
    assert resp.status_code == 422

def test_predict_unsupported_mime(client):
    data = {
        "question": "What is this?",
        "image": ("x.txt", BytesIO(b"not-an-image"), "text/plain"),
    }
    resp = client.post("/predict", data=data, content_type="multipart/form-data")
    assert resp.status_code == 415
