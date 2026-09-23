from llama_index.core.node_parser import MarkdownNodeParser
from llama_index.core.schema import Document, BaseNode

# Dung markdownnodeparser de chia file thanh cac node dua tren header
class MarkdownParser:

    def __init__(self):
        self.parser = MarkdownNodeParser()

    def parse(self, documents: list[Document]) -> list[BaseNode]:
        return self.parser.get_nodes_from_documents(documents)
    
    
#Cai nay de thu nghiem thoi
#chu van uu tien chia theo ngu nghia
