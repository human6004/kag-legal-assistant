import os
import time
from dotenv import load_dotenv
from typing import Any, Optional
from google import genai
from llama_index.core.llms.custom import CustomLLM
from llama_index.core.llms import CompletionResponse, LLMMetadata
from llama_index.core import Settings

load_dotenv()


class GeminiLLM(CustomLLM):
    """
    Wrapper tích hợp Google Gemini qua SDK chính thức google-genai.
    Hỗ trợ cơ chế tự động retry backoff và fallback model khi gặp 503/429.
    """
    model_name: str = "gemini-2.5-flash-lite"
    api_key: Optional[str] = None
    _client: Optional[Any] = None

    def __init__(self, model_name: str = "gemini-2.5-flash-lite", api_key: Optional[str] = None):
        super().__init__()
        self.model_name = model_name
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("Không tìm thấy GOOGLE_API_KEY trong biến môi trường hoặc tham số.")
        self._client = genai.Client(api_key=self.api_key)
        Settings.llm = self

    @property
    def metadata(self) -> LLMMetadata:
        return LLMMetadata(
            context_window=1000000,
            num_output=8192,
            model_name=self.model_name,
            is_chat_model=True
        )

    def complete(self, prompt: str, **kwargs: Any) -> CompletionResponse:
        candidate_models = [self.model_name, "gemini-1.5-flash", "gemini-2.0-flash"]
        last_exception = None

        for model in candidate_models:
            for attempt in range(3):
                try:
                    response = self._client.models.generate_content(
                        model=model,
                        contents=prompt
                    )
                    text_output = response.text or ""
                    return CompletionResponse(text=text_output)
                except Exception as e:
                    err_str = str(e).lower()
                    last_exception = e
                    if "503" in err_str or "high demand" in err_str or "429" in err_str or "quota" in err_str:
                        wait_sec = 1.5 * (attempt + 1)
                        print(f"[GEMINI] Gặp lỗi quá tải {model} ({e}), chờ {wait_sec}s thử lại...")
                        time.sleep(wait_sec)
                    else:
                        break

        print(f"[GEMINI] Cả các model dự phòng đều lỗi: {last_exception}")
        raise last_exception

    def stream_complete(self, prompt: str, **kwargs: Any):
        raise NotImplementedError("Streaming chưa được cấu hình cho CustomLLM này.")

    def get_llm(self):
        return self