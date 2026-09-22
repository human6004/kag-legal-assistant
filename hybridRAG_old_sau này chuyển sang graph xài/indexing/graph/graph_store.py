from llama_index.graph_stores.neo4j import Neo4jPropertyGraphStore
import os

from dotenv import load_dotenv

load_dotenv()



class GraphStore:

    def __init__(self):

        self.graph_store = Neo4jPropertyGraphStore(
            username=os.getenv("NEO4J_USERNAME"),
            password=os.getenv("NEO4J_PASSWORD"),
            url=os.getenv("NEO4J_URI"),
            # database=os.getenv("NEO4J_DATABASE"),
        )

    def get_store(self):
        return self.graph_store