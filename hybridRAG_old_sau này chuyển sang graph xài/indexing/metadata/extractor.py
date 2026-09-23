# from llama_index.core.extractors import (
#     TitleExtractor,
#     KeywordExtractor,
#     SummaryExtractor,
# )
# from llama_index.core.ingestion import IngestionPipeline

# #Buoc nay trich xuat metadata tu dong bang llama index thay vi hardcore viet metadata cung
# class MetadataExtractor:
#     def __init__(self):
#         self.pipeline = IngestionPipeline(
#             transformations=[
#                 TitleExtractor(nodes=3), 
#                 #TitleExtractor khong lay tieu de, ma dung 3 node dau de suy luan tieu de chung
#                 #de sau nay coi cho nay co the dieu chinh tang giam so node 
#                 KeywordExtractor(keywords=3), #sinh ra 3 tu khoa
#                 SummaryExtractor(summaries=["self"]), 
#                 #tom tat nut truoc, ban than no, nut sau no
#             ]
#         )

#     def extract(self, nodes):
#         return self.pipeline.run(nodes=nodes)
import os
import pickle
import time
from llama_index.core.extractors import TitleExtractor, KeywordExtractor, SummaryExtractor
from llama_index.core.ingestion import IngestionPipeline, IngestionCache
from llama_index.core.storage.kvstore import SimpleKVStore

CACHE_FILE = "metadata_cache.json"
FINAL_NODES_FILE = "metadata_nodes_final.pkl"


class MetadataExtractor:
    def __init__(self):
        if os.path.exists(CACHE_FILE):
            kvstore = SimpleKVStore.from_persist_path(CACHE_FILE)
            print(f"[CACHE] Tim thay cache cu tai {CACHE_FILE}")
        else:
            kvstore = SimpleKVStore()

        cache = IngestionCache(cache=kvstore)

        self.pipeline = IngestionPipeline(
            transformations=[
                TitleExtractor(nodes=3, num_workers=1),
                KeywordExtractor(keywords=3, num_workers=1),
                SummaryExtractor(summaries=["self"], num_workers=1),
            ],
            cache=cache,
        )

    def _find_problematic_node(self, nodes):
        """Chay tung node rieng le de tim chinh xac node nao gay loi"""
        print("[DEBUG] Dang do tung node de tim node loi...")
        for i, node in enumerate(nodes):
            try:
                single_pipeline = IngestionPipeline(
                    transformations=[KeywordExtractor(keywords=3, num_workers=1)],
                )
                single_pipeline.run(nodes=[node], show_progress=False)
            except IndexError:
                print(f"[DEBUG] Node loi tai vi tri {i}, id={node.node_id}")
                print(f"[DEBUG] Noi dung (200 ky tu dau): {node.text[:200]!r}")
                return i, node
        return None, None

    def extract(self, nodes, max_retries=2):
        if os.path.exists(FINAL_NODES_FILE):
            with open(FINAL_NODES_FILE, "rb") as f:
                saved_nodes = pickle.load(f)
            if len(saved_nodes) == len(nodes):
                print(f"[FINAL] Da co {len(saved_nodes)} node day du, load thang")
                return saved_nodes

        for attempt in range(max_retries):
            try:
                result = self.pipeline.run(nodes=nodes, show_progress=True)
                break
            except IndexError:
                print(f"\n[LOI] Lan thu {attempt + 1}/{max_retries} that bai, dang xac dinh node gay loi...")
                self.pipeline.cache.persist(CACHE_FILE)
                idx, bad_node = self._find_problematic_node(nodes)

                if bad_node is not None:
                    print(f"[LOI] Tim thay node gay loi tai vi tri {idx}")
                    print(f"[LOI] Metadata cua node: {bad_node.metadata.get('source', 'unknown')}")
                    print("[FIX] Se bo qua node nay (gan metadata rong) va tiep tuc")
                    bad_node.metadata["excerpt_keywords"] = ""
                    # Loai node loi ra khoi danh sach de pipeline chinh khong dam lai
                    nodes = [n for n in nodes if n.node_id != bad_node.node_id]
                    nodes.append(bad_node)  # dua vao cuoi, giu nguyen so luong
                else:
                    print("[LOI] Khong xac dinh duoc node cu the, thu lai toan bo")

                if attempt == max_retries - 1:
                    raise

        self.pipeline.cache.persist(CACHE_FILE)

        with open(FINAL_NODES_FILE, "wb") as f:
            pickle.dump(result, f)
        print(f"[FINAL] Da luu {len(result)} node vao {FINAL_NODES_FILE}")

        return result