import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.services.ai_brain import ai_service
from app.services.db import (
    get_supabase_client,
    get_all_knowledge_base,
    search_knowledge_base,
    search_knowledge_base_text,
    get_recent_call_sessions,
)

logger = logging.getLogger("kb_router")
router = APIRouter(prefix="/api/kb", tags=["Knowledge Base & Voice RAG"])


class KnowledgeDocCreate(BaseModel):
    content: str = Field(..., min_length=5, example="Astraventa provides 24/7 Voice AI Automation.")
    category: str = Field("services", example="services")
    metadata: Optional[Dict[str, Any]] = None


class RAGTestRequest(BaseModel):
    query: str = Field(..., example="What are your pricing packages?")
    match_threshold: float = Field(0.1, ge=0.0, le=1.0)
    match_count: int = Field(3, ge=1, le=10)


@router.get("")
async def list_knowledge_docs():
    """List all verified knowledge documents stored in Supabase."""
    docs = await get_all_knowledge_base(limit=100)
    return {"documents": docs, "total": len(docs)}


@router.post("")
async def add_knowledge_doc(req: KnowledgeDocCreate):
    """
    Inserts a new knowledge base document, generates 768d vector embedding,
    and saves to Supabase.
    """
    client = get_supabase_client()
    if not client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection unavailable",
        )

    try:
        # Generate embedding vector
        embedding = await ai_service.generate_embedding(req.content)
        if not embedding or len(embedding) == 0:
            embedding = [0.01] * 768

        meta = req.metadata or {}
        meta["category"] = req.category

        res = client.table("knowledge_base").insert({
            "content": req.content.strip(),
            "embedding": embedding,
            "metadata": meta,
        }).execute()

        new_doc = res.data[0] if res.data else {"content": req.content}
        return {"status": "success", "document": new_doc}
    except Exception as exc:
        logger.error(f"Error creating knowledge doc: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/{doc_id}")
async def delete_knowledge_doc(doc_id: str):
    """Deletes a knowledge document by ID."""
    client = get_supabase_client()
    if not client:
        raise HTTPException(status_code=503, detail="Database connection unavailable")

    try:
        client.table("knowledge_base").delete().eq("id", doc_id).execute()
        return {"status": "deleted", "id": doc_id}
    except Exception as exc:
        logger.error(f"Error deleting knowledge doc {doc_id}: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/test-query")
async def test_rag_query(req: RAGTestRequest):
    """
    Simulates what knowledge snippets the AI voice agent will retrieve
    when a caller asks this exact question during a phone call.
    """
    try:
        embedding = await ai_service.generate_embedding(req.query)
        matches = []
        if embedding:
            matches = await search_knowledge_base(
                query_embedding=embedding,
                match_threshold=req.match_threshold,
                match_count=req.match_count,
            )

        # Fallback to text search if empty
        if not matches:
            text_matches = await search_knowledge_base_text(req.query, limit=req.match_count)
            matches = [
                {
                    "id": m.get("id"),
                    "content": m.get("content"),
                    "metadata": m.get("metadata"),
                    "similarity": 0.85,  # Estimated text relevance
                }
                for m in text_matches
            ]

        return {
            "query": req.query,
            "match_count": len(matches),
            "results": matches,
        }
    except Exception as exc:
        logger.error(f"Error testing RAG query: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/call-sessions")
async def list_call_sessions():
    """Returns recent phone and WebRTC voice sessions."""
    sessions = await get_recent_call_sessions(limit=30)
    return {"sessions": sessions}
