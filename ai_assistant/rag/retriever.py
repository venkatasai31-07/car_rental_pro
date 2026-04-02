"""
══════════════════════════════════════════════════════════════════════════
  ROADMIND AI — RAG RETRIEVER
  File: ai_assistant/rag/retriever.py

  PLACE THIS FILE AT: your_project/ai_assistant/rag/retriever.py
  Do NOT run this file directly — it is imported by app.py.

  REQUIREMENTS: pip install chromadb google-generativeai
══════════════════════════════════════════════════════════════════════════
"""

import os
import chromadb
import google.generativeai as genai
from chromadb.utils import embedding_functions

CHROMA_STORE_PATH = os.path.join(os.path.dirname(__file__), "chroma_store")
COLLECTION_NAME   = "roadmind_knowledge"

# Must configure API key before calling — done in app.py via genai.configure(api_key=...)

# ── Embedding function (must match build_index.py) ─────────────────────────
class GeminiEmbeddingFunction(embedding_functions.EmbeddingFunction):
    def __call__(self, texts):
        embeddings = []
        for text in texts:
            result = genai.embed_content(
                model="models/gemini-embedding-001",
                content=text,
                task_type="retrieval_query"
            )
            embeddings.append(result["embedding"])
        return embeddings

# ── Initialize client once at module load ──────────────────────────────────
_client     = None
_collection = None

def get_collection():
    global _client, _collection
    if _collection is None:
        _client     = chromadb.PersistentClient(path=CHROMA_STORE_PATH)
        embed_func  = GeminiEmbeddingFunction()
        _collection = _client.get_collection(
            name=COLLECTION_NAME,
            embedding_function=embed_func
        )
    return _collection

# ── Main search function ───────────────────────────────────────────────────
def search_knowledge(query: str, top_k: int = 4) -> str:
    """
    Search the knowledge base for relevant content.
    Returns formatted string of top matching chunks.
    Returns empty string if nothing relevant found or if index is missing.
    """
    try:
        collection = get_collection()
        results    = collection.query(
            query_texts=[query],
            n_results=min(top_k, collection.count())
        )

        if not results or not results["documents"] or not results["documents"][0]:
            return ""

        # Filter by relevance (distance < 0.75 means reasonably relevant)
        relevant  = []
        docs      = results["documents"][0]
        distances = results["distances"][0]
        metas     = results["metadatas"][0]

        for doc, dist, meta in zip(docs, distances, metas):
            if dist < 0.75:
                source = meta.get("source", "platform")
                relevant.append(f"[From {source}]: {doc}")

        if not relevant:
            return ""

        return "\n\n---\n\n".join(relevant)

    except Exception as e:
        print(f"RAG search error: {e}")
        return ""   # Fail silently — Layer 3 (Gemini) will still answer
