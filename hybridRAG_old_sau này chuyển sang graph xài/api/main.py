from fastapi import FastAPI
from pydantic import BaseModel

from llm.nvidia import NvidiaNimLLM
from llm.answer_generator import AnswerGenerator

from retrieval.retrieve import Retriever
from database.neo4j_store import load_graph_index
from database.chroma_store import load_vector_index
from fastapi.middleware.cors import CORSMiddleware



llm = NvidiaNimLLM().get_llm()


vector_index = load_vector_index()
graph_index = load_graph_index()

retriever = Retriever(
    llm=llm,
    vector_index=vector_index,
    graph_index=graph_index
)

generator = AnswerGenerator()


app = FastAPI(
    title="GraphRAG API",
    version="1.0"
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],           # Cho phép tất cả (dùng cho dev)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
class ChatRequest(BaseModel):
    question: str


class ChatResponse(BaseModel):
    answer: str


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):

    contexts = retriever.retrieve(request.question)

    answer = generator.generate(
        question=request.question,
        contexts=contexts
    )

    return ChatResponse(
        answer=answer
    )