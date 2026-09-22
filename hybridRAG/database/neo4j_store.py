import os
from dotenv import load_dotenv
from llama_index.graph_stores.neo4j import Neo4jPropertyGraphStore
from llama_index.core import PropertyGraphIndex, Settings
from indexing.embedding.custom_model_embedding import CustomModelEmbedding

load_dotenv()


def get_neo4j_graph_store():
    """Kết nối Neo4j"""
    return Neo4jPropertyGraphStore(
        url=os.getenv("NEO4J_URI"),
        username=os.getenv("NEO4J_USERNAME"),
        password=os.getenv("NEO4J_PASSWORD"),
        database="neo4j"
    )


def load_graph_index():
    """Load PropertyGraphIndex từ Neo4j"""
    graph_store = get_neo4j_graph_store()

    # Khởi tạo embedding model thống nhất từ custom_model_embedding
    embed_model = CustomModelEmbedding().get_model()
    Settings.embed_model = embed_model

    # Load index đã build trước đó
    index = PropertyGraphIndex.from_existing(
        property_graph_store=graph_store,
        embed_model=embed_model,
        show_progress=True
    )
    return index