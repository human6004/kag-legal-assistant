# from llama_index.core import Settings
# from llama_index.llms.gemini import Gemini

# from llm.config import (
#     API_KEY,
#     MODEL_NAME,
# )


# class GeminiLLM:

#     def __init__(self):

#         self.llm = Gemini(
#             model=MODEL_NAME,
#             api_key=API_KEY,
#         )
#         #nạp đè llm mặc định của llamaindex
#         Settings.llm = self.llm


#     def get_llm(self):

#         return self.llm