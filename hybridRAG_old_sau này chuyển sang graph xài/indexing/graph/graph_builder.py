# from llama_index.core.indices.property_graph import PropertyGraphIndex, SchemaLLMPathExtractor
# from indexing.graph.graph_schema import entities, relations

# class GraphBuilder:
    
#     def __init__(self, llm, embed_model, graph_store):
#         self.llm = llm
#         self.embed_model = embed_model
#         self.graph_store = graph_store
    
#     def build(self, nodes):
#         print("GraphBuilder bat dau")
#         extractor = SchemaLLMPathExtractor(
#             llm=self.llm, 
#             possible_entities=entities,      # kiểu Literal, không phải list
#             possible_relations=relations,    # kiểu Literal, không phải list
#             strict=False,
#         )
#         print("Extractor tao xong")
#         graph= PropertyGraphIndex(
#             nodes=nodes,
#             llm=self.llm,
#             embed_model=self.embed_model,
#             property_graph_store=self.graph_store,
#             kg_extractors=[extractor],
                # show_progress=True,
#         )
#         print("Thong so o buoc PropertyGraphIndex thuoc file graph_builder.py")
#         print(type(nodes))
#         print(len(nodes))
#         print(type(nodes[0]))
#         print("Graph build xong")
#         return graph
import pickle
import os
import hashlib
from llama_index.core.indices.property_graph import PropertyGraphIndex, SchemaLLMPathExtractor
from indexing.graph.graph_schema import entities, relations
from indexing.rate_limit import RateLimiter

CHECKPOINT_FILE = "graph_progress.pkl"


class GraphBuilder:

    def __init__(self, llm, embed_model, graph_store):
        self.llm = llm
        self.embed_model = embed_model
        self.graph_store = graph_store
        # Tao rate limiter 1 LAN DUY NHAT khi khoi tao class, khong tao lai trong vong lap
        # 180/phut vi gpt-5.6-sol la subscription, thuong co gioi han cao hon NVIDIA free tier
        self.rate_limiter = RateLimiter(max_per_minute=180)

    def _stable_id(self, node):
        """ID on dinh dua theo noi dung, khong doi giua cac lan chay"""
        content = node.get_content()
        return hashlib.md5(content.encode("utf-8")).hexdigest()

    def _load_progress(self):
        if os.path.exists(CHECKPOINT_FILE):
            with open(CHECKPOINT_FILE, "rb") as f:
                done_ids = pickle.load(f)
            print(f"[CHECKPOINT] Da co {len(done_ids)} node tu truoc")
            return done_ids
        return set()

    def _save_progress(self, done_ids):
        tmp_file = CHECKPOINT_FILE + ".tmp"
        with open(tmp_file, "wb") as f:
            pickle.dump(done_ids, f)
        os.replace(tmp_file, CHECKPOINT_FILE)

    def build(self, nodes, batch_size=3):
        print("GraphBuilder bat dau")

        extractor = SchemaLLMPathExtractor(
            llm=self.llm,
            possible_entities=entities,
            possible_relations=relations,
            strict=False,
            num_workers=3,  # gpt-5.6-sol thuong chiu duoc song song tot hon NVIDIA free
        )
        print("Extractor tao xong")

        done_ids = self._load_progress()
        remaining_nodes = [n for n in nodes if self._stable_id(n) not in done_ids]

        print(f"Tong: {len(nodes)} | Da xong: {len(done_ids)} | Con lai: {len(remaining_nodes)}")

        graph = PropertyGraphIndex.from_existing(
            property_graph_store=self.graph_store,
            llm=self.llm,
            embed_model=self.embed_model,
            kg_extractors=[extractor],
        )

        if not remaining_nodes:
            print("Da xu ly het tu truoc")
            return graph

        for i in range(0, len(remaining_nodes), batch_size):
            batch = remaining_nodes[i:i + batch_size]
            print(f"Dang xu ly batch {i} -> {i + len(batch)} / {len(remaining_nodes)}")

            try:
                self.rate_limiter.wait()  # cho o day, khong tao lai object
                graph.insert_nodes(batch)
            except Exception as e:
                print(f"LOI o batch {i}: {e}")
                self._save_progress(done_ids)
                print("Da luu checkpoint, chay lai script se resume tu day.")
                raise

            done_ids.update(self._stable_id(n) for n in batch)
            self._save_progress(done_ids)
            print(f"Da ghi xong batch, tong da xong: {len(done_ids)} node")

        print("Graph build xong toan bo")
        if os.path.exists(CHECKPOINT_FILE):
            os.remove(CHECKPOINT_FILE)
            print("[CHECKPOINT] Da xoa vi hoan thanh")

        return graph