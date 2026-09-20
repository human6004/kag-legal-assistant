from bs4 import BeautifulSoup
from langchain_text_splitters import RecursiveCharacterTextSplitter, MarkdownHeaderTextSplitter, Se
import os
import re
from sentence_transformers import SentenceTransformer
import chromadb


md_folder = r"C:\Users\Duy\Documents\MyProject\chat_service_nckh\data"

md_files = [
    os.path.join(md_folder, f)
    for f in os.listdir(md_folder)
    if f.endswith(".md")
]

def load_md(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()
 
all_docs = []

for md in md_files:
    text = load_md(md)
    print(md) #test thôi
    all_docs.append({
        "source": md,
        "text": text
    })

chunks = []
metadata = [] #chuẩn bị metadata tốt là rất quan trọng 

#do cấu trúc page đã bị nhúng vô text rồi nên là dùng cách regex để lấy lại page
def extract_page(text):
    match = re.search(r"<page_number>(\d+)</page_number>", text)
    if match:
        return int(match.group(1))
    return None

for doc in all_docs:
    split_chunks = phanchiaNguNghia.split_text(doc["text"]) 



    for index, chunk in enumerate(split_chunks):
        chunks.append(chunk.page_content)
        metadata.append({
            "source": os.path.basename(doc["source"]),
            "page_number": extract_page(doc["text"]),
            "document_type": "mai_vang_handbook",
            "category": "plant_disease",
            "chunk_id": f"{os.path.basename(doc['source'])}_{index}"
        })

print("Total chunks:", len(chunks))
print("Noi dung ben trong:", chunks[0])


model = SentenceTransformer("BAAI/bge-m3")

embeddings = model.encode(
    chunks,
    batch_size=32,
    show_progress_bar=True
)


client = chromadb.PersistentClient(path="chroma_db_split_markdownheader")

collection = client.get_or_create_collection("cay_mai_md")


#lập chỉ mục
for i, chunk in enumerate(chunks):
    collection.add(
        documents=[chunk],
        embeddings=[embeddings[i].tolist()],
        ids=[f"md_chunk_{i}"],
        metadatas=[metadata[i]]
    )