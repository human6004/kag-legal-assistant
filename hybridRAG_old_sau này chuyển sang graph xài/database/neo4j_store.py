from llama_index.graph_stores.neo4j import Neo4jPropertyGraphStore
from llama_index.core import PropertyGraphIndex, Settings
from llama_index.embeddings.openai_like import OpenAILikeEmbedding
import os
from dotenv import load_dotenv

load_dotenv()

def get_neo4j_graph_store():
    """Kết nối Neo4j"""
    return Neo4jPropertyGraphStore(
        url=os.getenv("NEO4J_URI"),
        username=os.getenv("NEO4J_USERNAME"),
        password=os.getenv("NEO4J_PASSWORD"),   # nên để password trong .env
        database="neo4j"
    )


def load_graph_index():
    """Load PropertyGraphIndex từ Neo4j"""
    graph_store = get_neo4j_graph_store()

    # Khởi tạo embedding model
    embed_model = OpenAILikeEmbedding(
        model_name="nvidia/nv-embed-v1",
        api_base="https://integrate.api.nvidia.com/v1",
        api_key=os.getenv("NVIDIA_API_KEY2"),
        embed_batch_size=8,
        additional_kwargs={
            "extra_body": {
                "input_type": "query",
                "truncate": "END",
            }
        },
    )
    Settings.embed_model = embed_model

    # Load index đã build trước đó
    index = PropertyGraphIndex.from_existing(
        property_graph_store=graph_store,
        show_progress=True
    )
    return index