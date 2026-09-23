from llama_index.embeddings.openai_like import OpenAILikeEmbedding  # DUNG
from llama_index.core import Settings
import os
from dotenv import load_dotenv
load_dotenv()

Settings.chunk_size = 1024          # ← Khuyến nghị bắt đầu từ đây
Settings.chunk_overlap = 100
class NVIDIAEmbeddingWrapper:

    def __init__(self, input_type: str = "passage"):
        self.input_type = input_type
        self.embed_model = OpenAILikeEmbedding(
            model_name="nvidia/nv-embed-v1",
            api_base="https://integrate.api.nvidia.com/v1",
            api_key=os.getenv("NVIDIA_API_KEY2"),
            embed_batch_size=8,
            timeout=120.0,
            
            additional_kwargs={
                "extra_body": {
                    "input_type":   input_type,
                    "truncate": "END",
                }
            },
        )

        

    def get_model(self):
        Settings.embed_model = self.embed_model
        return self.embed_model