import os
import io
import base64
from abc import ABC, abstractmethod
from PIL import Image
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage

load_dotenv()

class VQAProvider(ABC):
    """Abstract base class for VQA model providers."""
    @abstractmethod
    def predict(self, image_b64: str, text: str) -> str:
        pass

class GeminiProvider(VQAProvider):
    """Google Gemini implementation of the VQA provider."""
    def __init__(self, model_name="gemini-2.5-flash"):
        if not os.getenv("GOOGLE_API_KEY"):
            print("Warning: GOOGLE_API_KEY not found in environment variables.")

        print(f"Initializing Gemini VQA Provider with model: {model_name}")
        self.llm = ChatGoogleGenerativeAI(model=model_name)

    def predict(self, image_b64: str, text: str) -> str:
        try:
            message = HumanMessage(
                content=[
                    {"type": "text", "text": text},
                    {
                        "type": "image_url",
                        "image_url": f"data:image/jpeg;base64,{image_b64}"
                    }
                ]
            )
            response = self.llm.invoke([message])
            return response.content
        except Exception as e:
            print(f"Gemini Provider Error: {e}")
            raise e

class VQAEngine:
    """
    Orchestrates VQA requests by delegating to a specific provider.
    """
    def __init__(self, provider: VQAProvider | None = None):
        # Default to Gemini if no provider is specified
        self.provider = provider or GeminiProvider(
            model_name=os.getenv("MODEL_NAME", "gemini-2.5-flash")
        )

    def predict(self, image_b64: str, text: str) -> str:
        """
        Executes the VQA chain using the provided base64 image and question.
        """
        try:
            print(f"Executing VQA Chain for question: '{text}'")
            return self.provider.predict(image_b64, text)
        except Exception as e:
            print(f"Engine Error: {e}")
            return f"Error processing request: {str(e)}"
