"""
Knowledge Base Router
─────────────────────
Endpoints for uploading, listing, and deleting PDF documents.
Supports two document categories: English and Sinhala.
PDFs are stored in MongoDB GridFS (secondary DB) and metadata is
tracked in separate collections per language.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List

from bson import ObjectId
from fastapi import APIRouter, HTTPException, UploadFile, File
from motor.motor_asyncio import AsyncIOMotorGridFSBucket

from database import secondary_database

# ── English router ───────────────────────────────────────────────────

english_router = APIRouter(
    prefix="/api/v1/english_docs",
    tags=["Knowledge Base — English"],
)

ENGLISH_COLLECTION = "knowledge_base_docs"

# ── Sinhala router ───────────────────────────────────────────────────

sinhala_router = APIRouter(
    prefix="/api/v1/sinhala_docs",
    tags=["Knowledge Base — Sinhala"],
)

SINHALA_COLLECTION = "knowledge_base_sinhala_docs"


# ── helpers ──────────────────────────────────────────────────────────

def _oid(value: str) -> ObjectId:
    """Convert a string to ObjectId or raise 400."""
    try:
        return ObjectId(value)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid document ID")


def _doc_out(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Serialise a metadata document for the API response."""
    return {
        "doc_id": str(doc["_id"]),
        "source": doc.get("source", ""),
        "file_size": doc.get("file_size", 0),
        "content_type": doc.get("content_type", "application/pdf"),
        "uploaded_at": doc.get("uploaded_at", ""),
    }


async def _upload(file: UploadFile, collection: str, gridfs_prefix: str):
    """Shared upload logic for both languages."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are accepted",
        )

    contents = await file.read()

    if len(contents) == 0:
        raise HTTPException(status_code=400, detail="File is empty")

    # Store binary in GridFS (secondary DB)
    fs = AsyncIOMotorGridFSBucket(
        secondary_database,
        bucket_name=gridfs_prefix,
    )
    grid_id = await fs.upload_from_stream(
        file.filename,
        contents,
        metadata={"content_type": file.content_type or "application/pdf"},
    )

    # Store metadata
    coll = secondary_database[collection]
    meta = {
        "source": file.filename,
        "gridfs_id": str(grid_id),
        "file_size": len(contents),
        "content_type": file.content_type or "application/pdf",
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
    }
    result = await coll.insert_one(meta)

    return {
        "message": "Document uploaded successfully",
        "doc_id": str(result.inserted_id),
        "source": file.filename,
    }


async def _list_documents(collection: str):
    """Shared list logic."""
    coll = secondary_database[collection]
    cursor = coll.find().sort("uploaded_at", -1)

    documents: List[Dict[str, Any]] = []
    async for doc in cursor:
        documents.append(_doc_out(doc))

    return {"documents": documents}


async def _get_document(doc_id: str, collection: str):
    """Shared get-one logic."""
    coll = secondary_database[collection]
    doc = await coll.find_one({"_id": _oid(doc_id)})

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    return _doc_out(doc)


async def _delete_document(doc_id: str, collection: str, gridfs_prefix: str):
    """Shared delete logic."""
    coll = secondary_database[collection]
    doc = await coll.find_one({"_id": _oid(doc_id)})

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Remove from GridFS
    gridfs_id = doc.get("gridfs_id")
    if gridfs_id:
        try:
            fs = AsyncIOMotorGridFSBucket(
                secondary_database,
                bucket_name=gridfs_prefix,
            )
            await fs.delete(ObjectId(gridfs_id))
        except Exception:
            pass

    await coll.delete_one({"_id": _oid(doc_id)})

    return {"message": "Document deleted", "doc_id": doc_id}


# ═════════════════════════════════════════════════════════════════════
#  ENGLISH ENDPOINTS
# ═════════════════════════════════════════════════════════════════════

@english_router.post("/upload")
async def upload_english_document(file: UploadFile = File(...)):
    """Upload an English PDF document."""
    return await _upload(file, ENGLISH_COLLECTION, "english_docs_fs")


@english_router.get("/documents")
async def list_english_documents():
    """Return all uploaded English documents."""
    return await _list_documents(ENGLISH_COLLECTION)


@english_router.get("/documents/{doc_id}")
async def get_english_document(doc_id: str):
    """Get metadata for a single English document."""
    return await _get_document(doc_id, ENGLISH_COLLECTION)


@english_router.delete("/documents/{doc_id}")
async def delete_english_document(doc_id: str):
    """Delete an English document."""
    return await _delete_document(doc_id, ENGLISH_COLLECTION, "english_docs_fs")


# ═════════════════════════════════════════════════════════════════════
#  SINHALA ENDPOINTS
# ═════════════════════════════════════════════════════════════════════

@sinhala_router.post("/upload")
async def upload_sinhala_document(file: UploadFile = File(...)):
    """Upload a Sinhala PDF document."""
    return await _upload(file, SINHALA_COLLECTION, "sinhala_docs_fs")


@sinhala_router.get("/documents")
async def list_sinhala_documents():
    """Return all uploaded Sinhala documents."""
    return await _list_documents(SINHALA_COLLECTION)


@sinhala_router.get("/documents/{doc_id}")
async def get_sinhala_document(doc_id: str):
    """Get metadata for a single Sinhala document."""
    return await _get_document(doc_id, SINHALA_COLLECTION)


@sinhala_router.delete("/documents/{doc_id}")
async def delete_sinhala_document(doc_id: str):
    """Delete a Sinhala document."""
    return await _delete_document(doc_id, SINHALA_COLLECTION, "sinhala_docs_fs")
