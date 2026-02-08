import os
import sys
import glob

# Ensure the project root is in the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from langchain_community.document_loaders import PyPDFLoader, TextLoader, UnstructuredMarkdownLoader
from agentforge.memory.vector_store import VectorStore

def ingest_documents():
    data_dir = "agentforge/data/knowledge_base"
    vector_store = VectorStore()
    
    files = glob.glob(os.path.join(data_dir, "**/*.*"), recursive=True)
    
    documents = []
    metadatas = []
    ids = []
    
    print(f"Found {len(files)} files to ingest.")
    
    for i, file_path in enumerate(files):
        try:
            print(f"Processing: {file_path}")
            if file_path.lower().endswith(".pdf"):
                loader = PyPDFLoader(file_path)
            elif file_path.lower().endswith(".md"):
                # Use TextLoader for markdown to avoid complex 'unstructured' dependencies
                loader = TextLoader(file_path, encoding="utf-8")
            elif file_path.lower().endswith(".txt"):
                loader = TextLoader(file_path, encoding="utf-8")
            else:
                print(f"Skipping unsupported file type: {file_path}")
                continue
                
            docs = loader.load_and_split()
            for j, doc in enumerate(docs):
                documents.append(doc.page_content)
                metadatas.append({
                    "source": file_path,
                    "page": doc.metadata.get("page", 0)
                })
                ids.append(f"{os.path.basename(file_path)}_{i}_{j}")
                
        except Exception as e:
            print(f"Error processing {file_path}: {e}")

    if documents:
        print(f"Adding {len(documents)} chunks to Vector Store...")
        vector_store.add_documents(documents, metadatas, ids)
        print("Ingestion complete.")
    else:
        print("No documents to ingest.")

if __name__ == "__main__":
    ingest_documents()
