# File này được giữ lại để tương thích ngược.
# Logic embedding chính đã được chuyển sang custom_model_embedding.py dùng Google Gemini Embedding.

from indexing.embedding.custom_model_embedding import CustomModelEmbedding, NVIDIAEmbeddingWrapper

__all__ = ["CustomModelEmbedding", "NVIDIAEmbeddingWrapper"]