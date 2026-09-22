
#Goi buoc load file vo, roi chuan hoa, lam sach may file markdown 
from ingestion.loader.load_markdown import MarkdownLoader
from ingestion.processes.clean_text import TextCleaner
from ingestion.processes.normalize import TextNormalizer

#Phan tich file markdown ra kem theo metadata nguyen thuy
from indexing.parser.markdown_parser import MarkdownParser
from indexing.metadata.extractor import MetadataExtractor

#Goi model embedding de chuyen may cai data vua phantich ra thanh graph theo mqh trong 
#schema quy dinh roi luu vao chroma
from indexing.embedding.bge_m3 import BGE_M3_Embedding
from indexing.embedding.embeddMD import NVIDIAEmbeddingWrapper
from indexing.graph.graph_builder import GraphBuilder
from indexing.vector.chroma import ChromaStore
from indexing.graph.graph_store import GraphStore
# from llm.gemini import GeminiLLM

from llama_index.core import Settings
from llm.ollama import OllamaLLM
from llm.nvidia import NvidiaNimLLM
from llama_index.core import VectorStoreIndex

class BuildIndex:

    def __init__(self):

        self.loader = MarkdownLoader("../data/processed")
        self.cleaner = TextCleaner()
        self.normalizer = TextNormalizer()

        self.parser = MarkdownParser()
        
        self.graph_store = GraphStore().get_store()
        self.llm = NvidiaNimLLM().get_llm()
        
        print(type(Settings.llm))
        print(Settings.llm.metadata.model_name)
        
        self.embed_model = NVIDIAEmbeddingWrapper(input_type="passage").get_model()
        
        self.metadata_extractor = MetadataExtractor()
        self.graph_builder = GraphBuilder(
            llm=self.llm,
            embed_model=self.embed_model,
            graph_store=self.graph_store
        )

        self.chroma_store = ChromaStore()

    def run(self):

        print("Dang load file markdown")
        documents = self.loader.load()

        print("Lam sach va chuan hoa")
        for doc in documents:
            cleaned_text = self.cleaner.clean(doc.text)
            normalized_text = self.normalizer.normalize(cleaned_text)
            doc.set_content(normalized_text)
        print("Phan tich")
        nodes = self.parser.parse(documents)

        print("Giai nen metadata")
        # Trước dòng: nodes = self.metadata_extractor.extract(nodes)
        print(f"[DEBUG] Số document load được: {len(documents)}")   # nếu có biến documents
        print(f"[DEBUG] Số node sau khi parse/chunk: {len(nodes)}")  # trước khi vào metadata extractor
        nodes = self.metadata_extractor.extract(nodes)
        print("So luong node metadata: ", len(nodes))
        print(f"Metadata node đầu tiên: {nodes[0].metadata}")
        print("Xay graph theo may cai mqh da quy dinh")
        graph_index = self.graph_builder.build(nodes)

        print("Lap chi muc vector")
        storage_context = self.chroma_store.get_storage_context()
        
        vector_index = VectorStoreIndex(
            nodes=nodes,
            storage_context=storage_context,
            embed_model=self.embed_model
        )

        print("Yeahhh hoan thanh, ngon chim luon")

        return graph_index, vector_index #Cho nay tra ve graph index voi vector index
    #dung 2 cai nay de bo sung cho nhau, moi cai co diem manh, yeu rieng
    