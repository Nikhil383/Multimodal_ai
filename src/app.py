import os
import base64
import io
import logging
from typing import Annotated

from fastapi import FastAPI, File, Form, UploadFile, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from PIL import Image, ImageFile, UnidentifiedImageError
from pydantic import BaseModel

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

app = FastAPI(title="Multimodal AI VQA")

# Mount static files and templates
app.mount("/static", StaticFiles(directory="src/static"), name="static")
templates = Jinja2Templates(directory="src/templates")

# Lazy initialization of VQA engine
_engine: VQAEngine | None = None

def get_engine() -> VQAEngine:
    global _engine
    if _engine is None:
        logger.info("Loading VQA Engine...")
        _engine = VQAEngine()
        logger.info("VQA Engine ready.")
    return _engine

def validate_and_process_image(file: UploadFile) -> str:
    """
    Validates image mime-type, size, and resizes if it exceeds MAX_IMAGE_DIMENSION.
    Returns base64 encoded JPEG string.
    """
    # 1. MIME Type Check
    if file.content_type not in ALLOWED_IMAGE_MIMES:
        raise HTTPException(status_code=415, detail=f"Unsupported image type: {file.content_type}")

    try:
        # 2. Read bytes and check size
        image_bytes = file.file.read()
        if len(image_bytes) > MAX_CONTENT_LENGTH:
            raise HTTPException(status_code=413, detail="Image too large")

        # 3. Open and verify
        image = Image.open(io.BytesIO(image_bytes))
        image.verify()

        # Re-open after verify() because it closes the file
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

        # 4. Resolution Capping (Resizing)
        # Resize if the longest side exceeds MAX_IMAGE_DIMENSION
        width, height = image.size
        if max(width, height) > MAX_IMAGE_DIMENSION:
            logger.info(f"Resizing image from {width}x{height} to fit within {MAX_IMAGE_DIMENSION}px")
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

    except UnidentifiedImageError:
        raise HTTPException(status_code=400, detail="Invalid or corrupted image")
    except Image.DecompressionBombError:
        raise HTTPException(status_code=413, detail="Image too large (decompression bomb)")
    except Exception as e:
        logger.exception("Image processing error")
        raise HTTPException(status_code=500, detail="Internal server error processing image")

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/predict")
async def predict(
    request: Request,
    image: UploadFile = File(...),
    question: str = Form(...)
):
    """
    Predicts answer for a given image and question.
    """
    try:
        # Validate and process image
        img_b64 = validate_and_process_image(image)

        # Engine prediction (called as a blocking op in a threadpool by FastAPI if not async)
        # Since VQAEngine.predict is synchronous, we'll use a threadpool (implicit in FastAPI
        # when using 'def' vs 'async def', but since this is 'async def', we should
        # wrap the synchronous call in run_in_threadpool or just use 'def predict')
        # However, to keep it truly async, we'll use a threadpool.

        from fastapi.concurrency import run_in_threadpool
        answer = await run_in_threadpool(get_engine().predict, img_b64, question)

        return {"answer": answer}

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.exception("Predict error")
        raise HTTPException(status_code=500, detail="Internal server error")

if __name__ == "__main__":
    import uvicorn
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "5000"))
    uvicorn.run(app, host=host, port=port)
