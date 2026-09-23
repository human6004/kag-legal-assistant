from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.core import Settings

class BGE_M3_Embedding:
    def __init__(self):
        self.embed_model = HuggingFaceEmbedding(
            model_name="BAAI/bge-m3"
        )
        Settings.embed_model = self.embed_model
    def get_model(self):
        return self.embed_model