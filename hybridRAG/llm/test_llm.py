from gemini import GeminiLLM
from nvidia import NvidiaNimLLM
llm = NvidiaNimLLM()

response = llm.complete(
    "Giới thiệu ngắn về cây mai vàng."
)

print(response)