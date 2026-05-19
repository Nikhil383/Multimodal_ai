import os
import time
from abc import ABC, abstractmethod
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
from google import genai
from google.genai import types

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
                        "image_url": f"data:image/jpeg;base64,{image_b64}",
                    },
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

    def predict_video(self, video_path: str, text: str) -> str:
        """
        Uploads local video to Gemini Files API, waits for processing,
        invokes the VQA query, and cleans up the uploaded file.
        """
        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not api_key:
            return "Error: Google API key not found in environment variables."

        client = None
        uploaded_file = None
        try:
            client = genai.Client(api_key=api_key)
            model_name = os.getenv("MODEL_NAME", "gemini-2.5-flash")

            print(f"Uploading local video: {video_path} to Gemini Files API...")
            import mimetypes

            mime_type, _ = mimetypes.guess_type(video_path)
            if not mime_type:
                if video_path.lower().endswith(".mov"):
                    mime_type = "video/quicktime"
                else:
                    mime_type = "video/mp4"

            upload_config = types.UploadFileConfig(mime_type=mime_type)
            uploaded_file = client.files.upload(file=video_path, config=upload_config)

            # Wait for file active
            start_time = time.time()
            poll_seconds = 5
            timeout_seconds = 600
            file_obj = uploaded_file

            while not file_obj.state or file_obj.state.name != "ACTIVE":
                if file_obj.state and file_obj.state.name == "FAILED":
                    raise RuntimeError(
                        f"Gemini video processing failed: {file_obj.name}"
                    )
                if time.time() - start_time > timeout_seconds:
                    raise TimeoutError(
                        f"Timed out waiting for Gemini to process: {file_obj.name}"
                    )

                print(
                    f"Processing video... current state={file_obj.state.name if file_obj.state else 'PENDING'}"
                )
                time.sleep(poll_seconds)
                file_obj = client.files.get(name=file_obj.name)

            print(f"Video ready: {file_obj.name}")

            prompt = f"""
You are a careful video visual question answering assistant.
Answer the user's question using only evidence from the video.
Mention relevant timestamps when they help support the answer.
If the video does not contain enough evidence, say that clearly.

Question: {text}
""".strip()

            print(f"Executing temporal Video VQA for model: {model_name}")
            response = client.models.generate_content(
                model=model_name, contents=[file_obj, prompt]
            )
            return response.text

        except Exception as e:
            print(f"Video VQA Error: {e}")
            return f"Error processing video: {str(e)}"
        finally:
            if client and uploaded_file:
                try:
                    client.files.delete(name=uploaded_file.name)
                    print(
                        f"Deleted uploaded file from Gemini Files API: {uploaded_file.name}"
                    )
                except Exception as delete_err:
                    print(
                        f"Warning: Failed to delete Gemini file {uploaded_file.name}: {delete_err}"
                    )

    def predict_youtube(self, youtube_url: str, text: str) -> str:
        """
        Invokes Gemini Video VQA directly using a public YouTube URL link.
        """
        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not api_key:
            return "Error: Google API key not found in environment variables."

        try:
            client = genai.Client(api_key=api_key)
            model_name = os.getenv("MODEL_NAME", "gemini-2.5-flash")

            # Construct Youtube video URI Part
            video_part = types.Part(file_data=types.FileData(file_uri=youtube_url))

            prompt = f"""
You are a careful video visual question answering assistant.
Answer the user's question using only evidence from the video.
Mention relevant timestamps when they help support the answer.
If the video does not contain enough evidence, say that clearly.

Question: {text}
""".strip()

            print(f"Executing YouTube VQA for URL: '{youtube_url}'")
            response = client.models.generate_content(
                model=model_name, contents=[video_part, prompt]
            )
            return response.text
        except Exception as e:
            print(f"YouTube VQA Error: {e}")
            return f"Error processing YouTube video: {str(e)}"
