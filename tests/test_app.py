from io import BytesIO
from unittest.mock import MagicMock, patch
import pytest
from PIL import Image
from src.app import app


def _make_jpeg_bytes() -> bytes:
    img = Image.new("RGB", (10, 10), color=(255, 0, 0))
    buf = BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture()
def client():
    # Setup mock VQAEngine
    with patch("src.app.VQAEngine") as mock_engine_cls:
        mock_engine = MagicMock()
        mock_engine.predict.return_value = "ok"
        mock_engine.predict_video.return_value = "video_ok"
        mock_engine.predict_youtube.return_value = "youtube_ok"
        mock_engine_cls.return_value = mock_engine

        # Reset lazy engine
        import src.app as app_module

        app_module._engine = None

        app.config["TESTING"] = True
        with app.test_client() as c:
            yield c


def test_predict_image_success(client):
    data = {"question": "What is this?"}
    data["image"] = (BytesIO(_make_jpeg_bytes()), "x.jpg")
    resp = client.post("/predict", data=data, content_type="multipart/form-data")
    assert resp.status_code == 200
    assert resp.json["answer"] == "ok"
    assert resp.json["metrics"]["type"] == "Image"


def test_predict_video_success(client):
    data = {"question": "What is this video about?"}
    data["video"] = (BytesIO(b"fake video data"), "x.mp4")
    resp = client.post("/predict", data=data, content_type="multipart/form-data")
    assert resp.status_code == 200
    assert resp.json["answer"] == "video_ok"
    assert resp.json["metrics"]["type"] == "Local Video"


def test_predict_youtube_success(client):
    data = {
        "question": "Describe this YouTube video.",
        "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    }
    resp = client.post("/predict", data=data, content_type="multipart/form-data")
    assert resp.status_code == 200
    assert resp.json["answer"] == "youtube_ok"
    assert resp.json["metrics"]["type"] == "YouTube Video"


def test_predict_missing_media(client):
    resp = client.post(
        "/predict", data={"question": "Hi"}, content_type="multipart/form-data"
    )
    assert resp.status_code == 400
    assert "error" in resp.json


def test_predict_missing_question(client):
    data = {"image": (BytesIO(_make_jpeg_bytes()), "x.jpg")}
    resp = client.post("/predict", data=data, content_type="multipart/form-data")
    assert resp.status_code == 400
    assert "error" in resp.json


def test_predict_unsupported_mime(client):
    data = {"question": "What is this?"}
    data["image"] = (BytesIO(b"not-an-image"), "x.txt")
    resp = client.post("/predict", data=data, content_type="multipart/form-data")
    assert resp.status_code in (400, 415)
