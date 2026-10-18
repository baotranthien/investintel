from __future__ import annotations

import hashlib
import json
import math
import os
import re
from abc import ABC, abstractmethod
from collections import Counter
from datetime import date
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.connection import SessionLocal
from database.models import Document, DocumentChunk


class VectorStore(ABC):
    """Repository interface for document retrieval backends."""

    @abstractmethod
    def index_documents(self, documents: list[dict[str, Any]]) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    def search(
        self,
        query: str,
        *,
        ticker: str | None = None,
        company: str | None = None,
        source: str | None = None,
        document_type: str | None = None,
        language: str | None = None,
        as_of_date: date | None = None,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError


class LocalEmbeddingProvider:
    """Local embedding abstraction. Falls back to a stable lexical feature vector when no configured model is installed."""

    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or os.getenv("OLLAMA_EMBEDDING_MODEL") or os.getenv("EMBEDDING_MODEL") or "NOT_CONFIGURED"
        self.status = "NOT_CONFIGURED" if self.model_name in {None, "", "NOT_CONFIGURED"} else "CONFIGURED"

    def embed(self, text: str) -> list[float]:
        if self.status == "NOT_CONFIGURED":
            raise RuntimeError("EMBEDDING_PROVIDER = NOT_CONFIGURED")

        tokens = re.findall(r"[a-zA-Z0-9]+", (text or "").lower())
        if not tokens:
            return [0.0] * 32

        counts = Counter(tokens)
        vector = [0.0] * 32
        for index, token in enumerate(sorted(counts)[:32]):
            token_hash = int(hashlib.md5(token.encode("utf-8")).hexdigest()[:8], 16)
            vector[index % 32] = float(counts[token]) * (1.0 + (token_hash % 1000) / 1000.0)
        return vector

    def describe(self) -> dict[str, Any]:
        return {
            "provider": "local-feature-vector",
            "status": self.status,
            "model": self.model_name if self.status == "CONFIGURED" else "NOT_CONFIGURED",
            "note": "No paid embedding API is used. If no local model is configured, the provider remains NOT_CONFIGURED.",
        }


class PGVectorStore(VectorStore):
    """Compatibility placeholder for a future PostgreSQL pgvector backend."""

    def __init__(self, session: Session | None = None):
        self.session = session or SessionLocal()

    def index_documents(self, documents: list[dict[str, Any]]) -> list[str]:
        raise RuntimeError("PGVectorStore is not configured in this local environment; PostgreSQL is BLOCKED.")

    def search(
        self,
        query: str,
        *,
        ticker: str | None = None,
        company: str | None = None,
        source: str | None = None,
        document_type: str | None = None,
        language: str | None = None,
        as_of_date: date | None = None,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        raise RuntimeError("PGVectorStore is not configured in this local environment; PostgreSQL is BLOCKED.")


class LocalVectorStore(VectorStore):
    """Local vector store backed by SQLite rows and deterministic lexical similarity."""

    def __init__(self, session: Session | None = None, embedding_provider: LocalEmbeddingProvider | None = None):
        self.session = session or SessionLocal()
        self.embedding_provider = embedding_provider or LocalEmbeddingProvider()

    def _document_filter(self, stmt, *, ticker=None, company=None, source=None, document_type=None, language=None, as_of_date=None):
        if ticker:
            stmt = stmt.filter(Document.ticker == ticker.upper())
        if company:
            stmt = stmt.filter(Document.company.ilike(f"%{company}%"))
        if source:
            stmt = stmt.filter(Document.source == source)
        if document_type:
            stmt = stmt.filter(Document.document_type == document_type)
        if language:
            stmt = stmt.filter(Document.language == language)
        if as_of_date:
            stmt = stmt.filter(Document.publication_date <= as_of_date)
        return stmt

    def _normalize_text(self, text: str) -> str:
        return re.sub(r"\s+", " ", (text or "")).strip()

    def _chunk_document(self, document: dict[str, Any]) -> list[dict[str, Any]]:
        raw_text = self._normalize_text(document.get("raw_text") or "")
        if not raw_text:
            return []

        section_name = "body"
        sections = re.split(r"\n\s*\n+", raw_text)
        chunks: list[dict[str, Any]] = []
        for index, section in enumerate(sections):
            cleaned = self._normalize_text(section)
            if not cleaned:
                continue
            if len(cleaned) <= 300:
                chunks.append({
                    "chunk_index": len(chunks),
                    "section": section_name,
                    "page_reference": document.get("page_reference") or None,
                    "text": cleaned,
                    "metadata": {"source": document.get("source"), "document_type": document.get("document_type")},
                })
                continue

            sections_by_paragraph = [part for part in re.split(r"(?<=[.!?])\s+", cleaned) if part]
            if len(sections_by_paragraph) == 1:
                sections_by_paragraph = [cleaned[i:i + 350] for i in range(0, len(cleaned), 350)]

            for paragraph_index, paragraph in enumerate(sections_by_paragraph):
                text = self._normalize_text(paragraph)
                if not text:
                    continue
                chunk_payload = {
                    "chunk_index": len(chunks),
                    "section": section_name,
                    "page_reference": document.get("page_reference") or None,
                    "text": text,
                    "metadata": {
                        "source": document.get("source"),
                        "document_type": document.get("document_type"),
                        "section_index": index,
                        "paragraph_index": paragraph_index,
                    },
                }
                if len(chunk_payload["text"]) > 1200:
                    chunk_payload["text"] = chunk_payload["text"][:1200]
                chunks.append(chunk_payload)
        return chunks

    def index_documents(self, documents: list[dict[str, Any]]) -> list[str]:
        ids: list[str] = []
        for document in documents:
            document_id = str(document.get("document_id") or document.get("id") or hashlib.sha256(json.dumps(document.get("metadata", {}), sort_keys=True).encode("utf-8")).hexdigest()[:12])
            existing = self.session.query(Document).filter(Document.document_id == document_id).first()
            if existing is None:
                record = Document(
                    document_id=document_id,
                    ticker=(document.get("ticker") or "").upper(),
                    company=document.get("company"),
                    source=document.get("source"),
                    publication_date=document.get("publication_date"),
                    period=document.get("period"),
                    document_type=document.get("document_type"),
                    language=document.get("language") or "en",
                    version=str(document.get("version") or "1"),
                    checksum=document.get("checksum") or hashlib.sha256((document.get("raw_text") or "").encode("utf-8")).hexdigest(),
                    title=document.get("title"),
                    raw_text=document.get("raw_text") or "",
                    status=document.get("status") or "READY",
                    is_synthetic=bool(document.get("is_synthetic")),
                    metadata_json=document.get("metadata") or {},
                )
                self.session.add(record)
                self.session.flush()
            else:
                record = existing

            document_chunks = self._chunk_document(document)
            for chunk in document_chunks:
                chunk_text = chunk["text"]
                embedding = []
                try:
                    embedding = self.embedding_provider.embed(chunk_text)
                    embedding_model = self.embedding_provider.model_name
                    embedding_version = "local-feature-vector-v1"
                except RuntimeError:
                    embedding = [0.0] * 32
                    embedding_model = "NOT_CONFIGURED"
                    embedding_version = "NOT_CONFIGURED"

                chunk_id = f"{document_id}-{chunk['chunk_index']}"
                existing_chunk = self.session.query(DocumentChunk).filter(DocumentChunk.chunk_id == chunk_id).first()
                if existing_chunk is None:
                    row = DocumentChunk(
                        document_id=document_id,
                        chunk_id=chunk_id,
                        section=chunk.get("section"),
                        page_reference=chunk.get("page_reference"),
                        text=chunk_text,
                        metadata_json=chunk.get("metadata") or {},
                        embedding_model=embedding_model,
                        embedding_version=embedding_version,
                        embedding=embedding,
                    )
                    self.session.add(row)
                else:
                    existing_chunk.text = chunk_text
                    existing_chunk.section = chunk.get("section")
                    existing_chunk.page_reference = chunk.get("page_reference")
                    existing_chunk.metadata_json = chunk.get("metadata") or {}
                    existing_chunk.embedding_model = embedding_model
                    existing_chunk.embedding_version = embedding_version
                    existing_chunk.embedding = embedding

            self.session.commit()
            ids.append(document_id)
        return ids

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        mag_a = math.sqrt(sum(x * x for x in a))
        mag_b = math.sqrt(sum(x * x for x in b))
        if mag_a == 0 or mag_b == 0:
            return 0.0
        return dot / (mag_a * mag_b)

    def _lexical_overlap(self, query_tokens: set[str], chunk_text: str) -> float:
        chunk_tokens = set(re.findall(r"[a-zA-Z0-9]+", chunk_text.lower()))
        if not chunk_tokens:
            return 0.0
        overlap = query_tokens & chunk_tokens
        return len(overlap) / max(1, len(query_tokens | chunk_tokens))

    def search(
        self,
        query: str,
        *,
        ticker: str | None = None,
        company: str | None = None,
        source: str | None = None,
        document_type: str | None = None,
        language: str | None = None,
        as_of_date: date | None = None,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        if not query or not query.strip():
            return []

        q_tokens = set(re.findall(r"[a-zA-Z0-9]+", query.lower()))
        query_vector = []
        try:
            query_vector = self.embedding_provider.embed(query)
        except RuntimeError:
            query_vector = [0.0] * 32

        stmt = select(DocumentChunk).join(Document)
        if ticker:
            stmt = stmt.where(Document.ticker == ticker.upper())
        if company:
            stmt = stmt.where(Document.company.ilike(f"%{company}%"))
        if source:
            stmt = stmt.where(Document.source == source)
        if document_type:
            stmt = stmt.where(Document.document_type == document_type)
        if language:
            stmt = stmt.where(Document.language == language)
        if as_of_date:
            stmt = stmt.where(Document.publication_date <= as_of_date)

        rows = self.session.execute(stmt).scalars().all()
        scored: list[dict[str, Any]] = []
        for row in rows:
            doc = self.session.query(Document).filter(Document.document_id == row.document_id).one_or_none()
            if doc is None:
                continue
            score = self._cosine_similarity(query_vector, row.embedding or [0.0] * 32)
            score += self._lexical_overlap(q_tokens, row.text) * 0.35
            if score <= 0 and not q_tokens.intersection(set(re.findall(r"[a-zA-Z0-9]+", row.text.lower()))):
                continue
            scored.append({
                "citation_id": row.chunk_id,
                "document_id": row.document_id,
                "chunk_id": row.chunk_id,
                "text": row.text,
                "score": round(score, 6),
                "source": doc.source,
                "publication_date": doc.publication_date.isoformat() if doc.publication_date else None,
                "ticker": doc.ticker,
                "company": doc.company,
                "document_type": doc.document_type,
                "language": doc.language,
                "section": row.section,
                "page_reference": row.page_reference,
                "metadata": row.metadata_json or {},
                "embedding_model": row.embedding_model,
                "embedding_version": row.embedding_version,
            })

        scored.sort(key=lambda item: (-item["score"], item["document_id"], item["chunk_id"]))
        return scored[:limit]


class DocumentRAGService:
    def __init__(self, session: Session | None = None, vector_store: VectorStore | None = None):
        self.session = session or SessionLocal()
        self.vector_store = vector_store or LocalVectorStore(session=self.session)

    @staticmethod
    def _synthetic_documents() -> list[dict[str, Any]]:
        return [
            {
                "document_id": "FPT-AR-2023-05",
                "ticker": "FPT",
                "company": "FPT Corporation",
                "source": "SYNTHETIC_FIXTURE",
                "publication_date": date(2023, 5, 1),
                "period": "FY2023",
                "document_type": "ANNUAL_REPORT",
                "language": "vi",
                "version": "1",
                "title": "FPT annual report fixture",
                "raw_text": "FPT annual report notes that software revenue grew strongly and the company maintained a resilient cash position. This document is clearly marked as a synthetic local fixture for development testing only.",
                "status": "READY",
                "is_synthetic": True,
                "metadata": {"source_notes": "SYNTHETIC_FIXTURE", "document_kind": "local-test"},
            },
            {
                "document_id": "FPT-AR-2023-09",
                "ticker": "FPT",
                "company": "FPT Corporation",
                "source": "SYNTHETIC_FIXTURE",
                "publication_date": date(2023, 9, 1),
                "period": "Q3-2023",
                "document_type": "FINANCIAL_REPORT",
                "language": "vi",
                "version": "1",
                "title": "FPT Q3 report fixture",
                "raw_text": "Recent FPT results show digital transformation demand and higher operating efficiency. This fixture is synthetic and must not be treated as a live official filing.",
                "status": "READY",
                "is_synthetic": True,
                "metadata": {"source_notes": "SYNTHETIC_FIXTURE", "document_kind": "local-test"},
            },
            {
                "document_id": "VCB-AR-2023-08",
                "ticker": "VCB",
                "company": "Vietcombank",
                "source": "SYNTHETIC_FIXTURE",
                "publication_date": date(2023, 8, 1),
                "period": "Q3-2023",
                "document_type": "FINANCIAL_REPORT",
                "language": "vi",
                "version": "1",
                "title": "VCB fixture",
                "raw_text": "Vietcombank liquidity and asset quality remained stable during the quarter. This fixture is synthetic and intended only for local vector retrieval tests.",
                "status": "READY",
                "is_synthetic": True,
                "metadata": {"source_notes": "SYNTHETIC_FIXTURE", "document_kind": "local-test"},
            },
        ]

    def seed_fixture_documents(self) -> list[str]:
        existing = self.session.query(Document).count()
        if existing:
            return [doc.document_id for doc in self.session.query(Document).all()]
        return self.vector_store.index_documents(self._synthetic_documents())

    def retrieve_documents(
        self,
        query: str,
        *,
        ticker: str | None = None,
        company: str | None = None,
        source: str | None = None,
        document_type: str | None = None,
        language: str | None = None,
        as_of_date: date | None = None,
        limit: int = 5,
    ) -> dict[str, Any]:
        if self.session.query(Document).count() == 0:
            self.seed_fixture_documents()

        hits = self.vector_store.search(
            query,
            ticker=ticker,
            company=company,
            source=source,
            document_type=document_type,
            language=language,
            as_of_date=as_of_date,
            limit=limit,
        )
        return {
            "status": "AVAILABLE" if hits else "INSUFFICIENT_DATA",
            "embedding_provider": self.vector_store.embedding_provider.describe(),
            "count": len(hits),
            "documents": hits,
        }


__all__ = [
    "VectorStore",
    "LocalVectorStore",
    "PGVectorStore",
    "LocalEmbeddingProvider",
    "DocumentRAGService",
]
