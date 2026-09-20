import os

from dotenv import load_dotenv
from langchain_google_genai import (ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings)

from langchain_community.vectorstores import Chroma

load_dotenv()

embedding = GoogleGenerativeAIEmbeddings(
    model = "models/gemini-embedding-2"
)
db= Chroma(
    persist_directory="vector_db",
    embedding_function=embedding
)
retriever = db.as_retriever(
    search_kwargs={"k":3}
)


llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash-lite",
    temperature=0
)

def ask(question):
    docs = retriever.invoke(question) #goi model

    context="\n\n".join(
        [
            d.page_content
            for d in docs
        ]
    )



    prompt=f"""

        Bạn là chuyên gia về kiểm thử phần mềm. Chỉ trả lời dựa trên dữ liệu bên dưới. 
        Nếu dữ liệu không có, hãy nói không tìm thấy thông tin.
        
        Hãy trả lời bằng cách:
        - tóm tắt ý chính
        - giải thích dễ hiểu
        - không chép nguyên văn

        Chỉ sử dụng context.

        CONTEXT:
        {context}
        CÂU HỎI:
        {question}

    """


    response=llm.invoke(prompt)


    return response.content
