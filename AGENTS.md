# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Common Commands

- **Install dependencies**: `make install` or `uv sync`
- **Run application**: `make run` or `uv run python -m src.app`
- **Run tests**: `make test` or `uv run pytest`
- **Lint and format**: `make format` (uses `ruff`)
- **Build Docker image**: `make docker-build`

## Architecture

The project follows a three-layer design for a Visual Question Answering (VQA) system:

1.  **Transport Layer (`src/app.py`)**: A Flask REST API that handles HTTP requests, validates image uploads, and encodes images into base64 data URIs.
2.  **Intelligence Layer (`src/model.py`)**: The VQA Engine that uses LangChain to construct multimodal prompts and orchestrate the interaction with the AI model.
3.  **External API**: Integration with Google Gemini Vision API for multimodal LLM inference and response parsing.

### Key Design Patterns
- **Separation of Concerns**: The web layer is isolated from the AI logic, allowing for independent testing and easy swapping of the LLM provider.
- **Mock-based Testing**: Tests in the `tests/` directory use `unittest.mock` to simulate API responses, ensuring CI/CD pipelines run without incurring API costs.
- **Data URI Pattern**: Images are processed as `data:image/jpeg;base64,{encoded}` for compatibility with the Gemini API.

## Project Structure

- `src/`: Core application logic.
    - `app.py`: Flask API and routing.
    - `model.py`: VQA Engine and AI orchestration.
    - `templates/`: HTML frontend.
    - `static/`: Frontend assets (CSS/JS).
- `tests/`: Unit tests with mocked API calls.
- `notebooks/`: Research and experimental notebooks.
- `pyproject.toml` / `uv.lock`: Project configuration and dependency locking via `uv`.
