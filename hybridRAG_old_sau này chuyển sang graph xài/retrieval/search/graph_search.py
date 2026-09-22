from llama_index.core.indices.property_graph import PropertyGraphIndex


class GraphSearch:

    def __init__(self, graph_index: PropertyGraphIndex, top_k: int = 5):
        self.graph_index = graph_index
        self.top_k = top_k

    def search(self, question: str):
        print("Buoc graph search")
        retriever = self.graph_index.as_retriever(
            similarity_top_k=self.top_k
        )

        return retriever.retrieve(question)