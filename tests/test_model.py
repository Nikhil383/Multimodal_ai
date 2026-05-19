import base64
import io
from unittest.mock import MagicMock, patch

from PIL import Image
from src.model import VQAEngine


@patch("src.model.ChatGoogleGenerativeAI")
def test_predict_success(mock_llm_cls):
    # Setup mock
    mock_llm = MagicMock()
    mock_llm_cls.return_value = mock_llm

    # Mock return value
    mock_response = MagicMock()
    mock_response.content = "A cat."
    mock_llm.invoke.return_value = mock_response

    # Initialize engine
    # We ignore API key warning in tests since we mock LLM
    with patch.dict("os.environ", {"GOOGLE_API_KEY": "fake_key"}):
        # Use default GeminiProvider via VQAEngine
        engine = VQAEngine()

    # Create fake image and convert to base64
    img = Image.new("RGB", (10, 10))
    buffered = io.BytesIO()
    img.save(buffered, format="JPEG")
    img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")

    # Run predict
    result = engine.predict(img_str, "What is this?")

    # Verify
    assert result == "A cat."
    mock_llm.invoke.assert_called_once()

    # Check if image was passed in payload (we can check args)
    call_args = mock_llm.invoke.call_args
    assert call_args is not None
    messages = call_args[0][0]
    assert len(messages) == 1
    assert isinstance(messages[0].content, list)
    assert messages[0].content[0]["type"] == "text"
    assert messages[0].content[1]["type"] == "image_url"


@patch("src.model.ChatGoogleGenerativeAI")
def test_predict_error(mock_llm_cls):
    # Test error handling - model catches exceptions and returns error message
    mock_llm = MagicMock()
    mock_llm_cls.return_value = mock_llm

    # Force an error
    mock_llm.invoke.side_effect = Exception("API Error")

    with patch.dict("os.environ", {"GOOGLE_API_KEY": "fake_key"}):
        engine = VQAEngine()

    result = engine.predict("fake_base64", "Question")
    assert "Error processing request" in result
