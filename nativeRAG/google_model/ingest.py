import os
from langchain_community.vectorstores import Chroma #nhap vao vectorDB
from langchain_google_genai import GoogleGenerativeAIEmbeddings  #nhung Google AI Studio vao
from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader #doc pdf
from langchain_text_splitters import RecursiveCharacterTextSplitter, MarkdownHeaderTextSplitter #phan chia cac text thanh chunk

load_dotenv() 

load_pdf= PyPDFLoader("../data/test.pdf")
documents = load_pdf.load()

#Khuc nay la phan chia thanh cac chunk 
#Cách cũ chia theo dấu \n không hiệu quả
# phanchia = RecursiveCharacterTextSplitter(
#     chunk_size=800,
#     chunk_overlap= 150,
# )
headers = {
    ("#", "h1"),
    ("##", "h2"),
}
phanchiaMarkDown = MarkdownHeaderTextSplitter(headers_to_split_on=headers, strip_headers= False)

chunks = phanchiaMarkDown.split_documents(documents)


#Nhung Googel AI 
embedding = GoogleGenerativeAIEmbeddings(
    model="models/gemini-embedding-2" #model embedding chuyen doc pdf 
    #chi tiet model o day https://ai.google.dev/gemini-api/docs/models/gemini-embedding-2?hl=vi
)

#tao vectorDB
db = Chroma.from_documents(
    documents=chunks,
    embedding=embedding,
    persist_directory="vector_db"
)

db.persist()

print("Đa tao thanh cong vector database",len(chunks))
