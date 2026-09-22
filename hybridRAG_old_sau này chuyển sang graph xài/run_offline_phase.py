# import os
# os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
# os.environ["OMP_NUM_THREADS"] = "1" 


from indexing.build_index import BuildIndex


# # # Init LLM trước
# # # GeminiLLM()
# # OllamaLLM()
# # # Init embedding trước
# # BGE_M3_Embedding()

print("Bat dau chạy")
builder = BuildIndex()

builder.run()
# print("HELLO")

# raise Exception("TEST")