import os
import logging
import hashlib
from typing import List

logger = logging.getLogger(__name__)

CHROMA_DIR = "/app/chroma_data"


def _get_client():
    import chromadb
    return chromadb.PersistentClient(path=CHROMA_DIR)


def _get_collection(user_id: int):
    client = _get_client()
    return client.get_or_create_collection(
        name=f"user_{user_id}",
        metadata={"hnsw:space": "cosine"}
    )


def _embed(texts: List[str]) -> List[List[float]]:
    """Simple TF-IDF-like embedding via sentence-transformers"""
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("all-MiniLM-L6-v2")
        return model.encode(texts).tolist()
    except Exception as e:
        logger.error(f"Embedding error: {e}")
        return [[0.0] * 384 for _ in texts]


def _chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i:i + chunk_size])
        chunks.append(chunk)
        i += chunk_size - overlap
    return chunks


async def add_text_to_kb(user_id: int, text: str, source: str = "manual") -> int:
    """Добавить текст в базу знаний"""
    chunks = _chunk_text(text)
    if not chunks:
        return 0

    collection = _get_collection(user_id)
    embeddings = _embed(chunks)

    ids = [hashlib.md5(f"{source}_{i}_{chunk[:50]}".encode()).hexdigest()
           for i, chunk in enumerate(chunks)]

    collection.upsert(
        ids=ids,
        documents=chunks,
        embeddings=embeddings,
        metadatas=[{"source": source, "chunk": i} for i in range(len(chunks))]
    )
    return len(chunks)


async def add_pdf_to_kb(user_id: int, pdf_bytes: bytes, filename: str) -> int:
    """Парсим PDF и добавляем в базу знаний"""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        full_text = ""
        for page in doc:
            full_text += page.get_text() + "\n"
        doc.close()

        if not full_text.strip():
            return 0

        return await add_text_to_kb(user_id, full_text, source=filename)
    except Exception as e:
        logger.error(f"PDF parse error: {e}")
        return 0


async def search_kb(user_id: int, query: str, top_k: int = 4) -> str:
    """Поиск релевантных кусков из базы знаний"""
    try:
        collection = _get_collection(user_id)
        count = collection.count()
        if count == 0:
            return ""

        embeddings = _embed([query])
        results = collection.query(
            query_embeddings=embeddings,
            n_results=min(top_k, count),
        )

        if not results["documents"] or not results["documents"][0]:
            return ""

        chunks = results["documents"][0]
        sources = [m.get("source", "unknown") for m in results["metadatas"][0]]

        context_parts = []
        for chunk, source in zip(chunks, sources):
            context_parts.append(f"[из: {source}]\n{chunk}")

        return "\n\n---\n\n".join(context_parts)
    except Exception as e:
        logger.error(f"Search KB error: {e}")
        return ""


async def delete_user_kb(user_id: int):
    """Очистить базу знаний пользователя"""
    try:
        client = _get_client()
        client.delete_collection(f"user_{user_id}")
    except Exception as e:
        logger.error(f"Delete KB error: {e}")
