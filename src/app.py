import os
import io
import time
import base64
import logging
import tempfile
from flask import Flask, render_template, request, jsonify
from PIL import Image, ImageFile, UnidentifiedImageError
from src.model import VQAEngine

# Configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", str(10 * 1024 * 1024)))
ALLOWED_IMAGE_MIMES = {"image/jpeg", "image/png", "image/webp"}
MAX_IMAGE_DIMENSION = int(os.getenv("MAX_IMAGE_DIMENSION", "2048"))

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("multimodal_ai")

# PIL safety: protect against decompression bombs.
Image.MAX_IMAGE_PIXELS = int(os.getenv("MAX_IMAGE_PIXELS", str(20_000_000)))
ImageFile.LOAD_TRUNCATED_IMAGES = False

app = Flask(__name__)
# Limit standard request body size (Flask will return 413 if exceeded)
app.config["MAX_CONTENT_LENGTH"] = (
    30 * 1024 * 1024
)  # Max 30MB total to allow 25MB video uploads

# Lazy initialization of VQA engine
_engine: VQAEngine | None = None


def get_engine() -> VQAEngine:
    global _engine
    if _engine is None:
        logger.info("Loading VQA Engine...")
        _engine = VQAEngine()
        logger.info("VQA Engine ready.")
    return _engine


def validate_and_process_image(file) -> str:
    """
    Validates image mime-type, size, and resizes if it exceeds MAX_IMAGE_DIMENSION.
    Returns base64 encoded JPEG string.
    """
    # 1. MIME Type Check
    if file.mimetype not in ALLOWED_IMAGE_MIMES:
        raise ValueError(f"Unsupported image type: {file.mimetype}")

    # 2. Read bytes and check size
    image_bytes = file.read()
    if len(image_bytes) > MAX_CONTENT_LENGTH:
        raise ValueError("Image file too large (Max 10MB)")

    # 3. Open and verify
    image = Image.open(io.BytesIO(image_bytes))
    image.verify()

    # Re-open after verify() because it closes the file
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

    # 4. Resolution Capping (Resizing)
    width, height = image.size
    if max(width, height) > MAX_IMAGE_DIMENSION:
        logger.info(
            f"Resizing image from {width}x{height} to fit within {MAX_IMAGE_DIMENSION}px"
        )
        if width > height:
            new_width = MAX_IMAGE_DIMENSION
            new_height = int(height * (MAX_IMAGE_DIMENSION / width))
        else:
            new_height = MAX_IMAGE_DIMENSION
            new_width = int(width * (MAX_IMAGE_DIMENSION / height))

        image = image.resize((new_width, new_height), Image.LANCZOS)

    # 5. Convert to Base64 JPEG
    buffered = io.BytesIO()
    image.save(buffered, format="JPEG", quality=85)
    return base64.b64encode(buffered.getvalue()).decode("utf-8")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/predict", methods=["POST"])
def predict():
    """
    Unified endpoint to handle Image VQA, Video VQA (local upload), or YouTube VQA queries.
    """
    start_time = time.time()
    question = request.form.get("question", "").strip()

    if not question:
        return jsonify({"error": "Please ask a question."}), 400

    # 1. Case A: YouTube URL is provided
    youtube_url = request.form.get("youtube_url", "").strip()
    if youtube_url:
        try:
            answer = get_engine().predict_youtube(youtube_url, question)
            elapsed_time = round(time.time() - start_time, 2)
            return jsonify(
                {
                    "answer": answer,
                    "metrics": {
                        "model": os.getenv("MODEL_NAME", "gemini-2.5-flash"),
                        "time": f"{elapsed_time}s",
                        "type": "YouTube Video",
                    },
                }
            )
        except Exception as e:
            logger.exception("YouTube VQA controller error")
            return jsonify({"error": str(e)}), 500

    # 2. Case B: Video file is uploaded
    if "video" in request.files and request.files["video"].filename != "":
        video_file = request.files["video"]
        # Max video size: 25MB
        MAX_VIDEO_SIZE = 25 * 1024 * 1024

        # Read video bytes to check size
        video_bytes = video_file.read()
        if len(video_bytes) > MAX_VIDEO_SIZE:
            return jsonify({"error": "Video file too large (Max 25MB)"}), 413

        # Reset file pointer
        video_file.seek(0)

        # Check MIME type and file extension
        ALLOWED_VIDEO_MIMES = {
            "video/mp4",
            "video/webm",
            "video/quicktime",
            "video/mov",
        }
        content_type = video_file.content_type
        is_valid_ext = video_file.filename.lower().endswith(
            (".mp4", ".webm", ".mov", ".avi")
        )

        if content_type not in ALLOWED_VIDEO_MIMES and not is_valid_ext:
            return jsonify(
                {"error": f"Unsupported video type: {content_type or 'unknown'}"}
            ), 415

        # Create temporary file to store video
        temp_dir = tempfile.gettempdir()
        suffix = os.path.splitext(video_file.filename)[1]
        temp_file_handle, temp_file_path = tempfile.mkstemp(suffix=suffix, dir=temp_dir)

        try:
            with os.fdopen(temp_file_handle, "wb") as temp_file:
                temp_file.write(video_bytes)

            # Predict from video
            answer = get_engine().predict_video(temp_file_path, question)
            elapsed_time = round(time.time() - start_time, 2)
            return jsonify(
                {
                    "answer": answer,
                    "metrics": {
                        "model": os.getenv("MODEL_NAME", "gemini-2.5-flash"),
                        "time": f"{elapsed_time}s",
                        "type": "Local Video",
                    },
                }
            )
        except Exception as e:
            logger.exception("Video VQA controller error")
            return jsonify({"error": str(e)}), 500
        finally:
            # Clean up local temp file
            if os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                    logger.info(f"Removed temporary local video file: {temp_file_path}")
                except Exception as rm_e:
                    logger.warning(
                        f"Failed to remove temp file {temp_file_path}: {rm_e}"
                    )

    # 3. Case C: Image file is uploaded
    if "image" in request.files and request.files["image"].filename != "":
        image_file = request.files["image"]
        try:
            img_b64 = validate_and_process_image(image_file)
            answer = get_engine().predict(img_b64, question)
            elapsed_time = round(time.time() - start_time, 2)
            return jsonify(
                {
                    "answer": answer,
                    "metrics": {
                        "model": os.getenv("MODEL_NAME", "gemini-2.5-flash"),
                        "time": f"{elapsed_time}s",
                        "type": "Image",
                    },
                }
            )
        except ValueError as val_err:
            return jsonify({"error": str(val_err)}), 400
        except UnidentifiedImageError:
            return jsonify({"error": "Invalid or corrupted image"}), 400
        except Image.DecompressionBombError:
            return jsonify({"error": "Image file too large (decompression bomb)"}), 413
        except Exception:
            logger.exception("Image VQA controller error")
            return jsonify({"error": "Internal server error processing image"}), 500

    # No media input provided
    return jsonify(
        {"error": "Please upload an image, a video, or provide a YouTube URL."}
    ), 400


if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "").lower() in {"1", "true", "yes", "on"}
    app.run(host=host, port=port, debug=debug)
