

class VectorSearch:

    def __init__(self, vector_index,top_k: int = 5):

        self.vector_index = vector_index
        self.top_k = top_k

    def search(self, question):
        print("Buoc vector search")
        retriever = self.vector_index.as_retriever(
            similarity_top_k= self.top_k
        )

        return retriever.retrieve(question)