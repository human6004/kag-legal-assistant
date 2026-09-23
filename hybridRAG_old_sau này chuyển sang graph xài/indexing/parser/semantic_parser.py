from llama_index.core.node_parser import SemanticSplitterNodeParser
from llama_index.core.schema import Document, BaseNode

# chia tai lieu theo ngu nghia thay vi dung cach cu la markdownsplit 

class SemanticParser:

    def __init__(self, embed_model):

        self.parser = SemanticSplitterNodeParser( # cach nay ngon chim hon nhieu
            embed_model=embed_model, #truyen model tu thu muc embedding
            buffer_size=1,
            breakpoint_percentile_threshold=95,
        )

    def parse(self, documents: list[Document]) -> list[BaseNode]:
        return self.parser.get_nodes_from_documents(documents)