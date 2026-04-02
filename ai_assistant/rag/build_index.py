"""
══════════════════════════════════════════════════════════════════════════
  ROADMIND AI — RAG INDEX BUILDER
  File: ai_assistant/rag/build_index.py

  PLACE THIS FILE AT: your_project/ai_assistant/rag/build_index.py

  RUN ONCE before starting your server:
      python ai_assistant/rag/build_index.py

  Re-run whenever you add/edit .txt files in ai_assistant/knowledge/

  REQUIREMENTS: pip install chromadb google-generativeai
══════════════════════════════════════════════════════════════════════════
"""

import os
import chromadb
from chromadb.utils import embedding_functions
import google.generativeai as genai

# ── Config ─────────────────────────────────────────────────────────────────
GEMINI_API_KEY    = os.environ.get("GEMINI_API_KEY", "AIzaSyDT9cCkLw4RdNmc73F9L0HJJMrMWtuRESM")
KNOWLEDGE_DIR     = os.path.join(os.path.dirname(__file__), "../knowledge")
CHROMA_STORE_PATH = os.path.join(os.path.dirname(__file__), "chroma_store")
COLLECTION_NAME   = "roadmind_knowledge"
CHUNK_SIZE        = 400    # characters per chunk
CHUNK_OVERLAP     = 80     # overlap between chunks for context continuity

genai.configure(api_key=GEMINI_API_KEY)

# ── Embedding function using Gemini ────────────────────────────────────────
class GeminiEmbeddingFunction(embedding_functions.EmbeddingFunction):
    def __call__(self, texts):
        embeddings = []
        for text in texts:
            result = genai.embed_content(
                model="models/gemini-embedding-001",
                content=text,
                task_type="retrieval_document"
            )
            embeddings.append(result["embedding"])
        return embeddings

# ── Text chunking ──────────────────────────────────────────────────────────
def chunk_text(text, source_file):
    """Split text into overlapping chunks with source metadata"""
    chunks = []
    ids    = []
    metas  = []

    # Split by double newline first (natural paragraph breaks)
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    current_chunk = ""
    chunk_index   = 0

    for para in paragraphs:
        if len(current_chunk) + len(para) < CHUNK_SIZE:
            current_chunk += "\n\n" + para if current_chunk else para
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
                ids.append(f"{source_file}_{chunk_index}")
                metas.append({"source": source_file, "chunk": chunk_index})
                chunk_index += 1
                # Start new chunk with overlap
                words = current_chunk.split()
                overlap_text = " ".join(words[-CHUNK_OVERLAP:])
                current_chunk = overlap_text + "\n\n" + para
            else:
                current_chunk = para

    # Don't forget the last chunk
    if current_chunk.strip():
        chunks.append(current_chunk.strip())
        ids.append(f"{source_file}_{chunk_index}")
        metas.append({"source": source_file, "chunk": chunk_index})

    return chunks, ids, metas

# ── Main build function ────────────────────────────────────────────────────
def build_index():
    print("Building RoadMind knowledge index...")

    # Initialize ChromaDB
    client     = chromadb.PersistentClient(path=CHROMA_STORE_PATH)
    embed_func = GeminiEmbeddingFunction()

    # Delete existing collection to rebuild fresh
    try:
        client.delete_collection(COLLECTION_NAME)
        print("  Cleared existing index")
    except:
        pass

    collection = client.create_collection(
        name=COLLECTION_NAME,
        embedding_function=embed_func,
        metadata={"hnsw:space": "cosine"}
    )

    # Process each .txt file in knowledge/
    if not os.path.exists(KNOWLEDGE_DIR):
        os.makedirs(KNOWLEDGE_DIR)
        print(f"  Created knowledge/ folder at: {KNOWLEDGE_DIR}")
        print("  Add your .txt knowledge files and re-run this script.")
        return

    txt_files = [f for f in os.listdir(KNOWLEDGE_DIR) if f.endswith(".txt")]

    if not txt_files:
        print("No .txt files found in knowledge/ folder")
        print("Add your platform policy and guide .txt files there and re-run.")
        return

    total_chunks = 0

    for filename in txt_files:
        filepath = os.path.join(KNOWLEDGE_DIR, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            text = f.read()

        source_name        = filename.replace(".txt", "")
        chunks, ids, metas = chunk_text(text, source_name)

        if chunks:
            collection.upsert(
                ids=ids,
                documents=chunks,
                metadatas=metas
            )
            print(f"  {filename} -> {len(chunks)} chunks indexed")
            total_chunks += len(chunks)

    print(f"\nIndex built successfully!")
    print(f"   Total chunks: {total_chunks}")
    print(f"   Stored at: {CHROMA_STORE_PATH}")
    print(f"\nRe-run this script whenever you edit knowledge/ files.")

if __name__ == "__main__":
    build_index()
