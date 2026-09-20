from fastapi import FastAPI

from pydantic import BaseModel


from fastAPI.old_code.google_model.rag import ask



app=FastAPI(
    title="Mai Vang Vinahouse RAG API"
)

class Question(BaseModel):

    text:str

@app.get("/")
def home():

    return {
        "status":"running"
    }



@app.post("/chat")
def chat(
    q:Question
):
    answer=ask(
        q.text
    )
    return {
        "question":q.text,
        "answer":answer
    }