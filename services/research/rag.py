from __future__ import annotations

from abc import ABC, abstractmethod
from collections import Counter
from datetime import date
import hashlib
import json
import math
import os
from pathlib import Path
import re
from typing import Any
import unicodedata

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.connection import SessionLocal
from database.models import Document, DocumentChunk


def _strip_vietnamese_accents(text: str) -> str:
    """Normalizes Vietnamese diacritics to accentless lowercase ASCII for robust lexical matching."""
    if not text:
        return ""
    text = text.replace("đ", "d").replace("Đ", "D")
    decomposed = unicodedata.normalize("NFD", text)
    stripped = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return unicodedata.normalize("NFC", stripped)


def _tokenize_rag(text: str) -> list[str]:
    """Accent-insensitive tokenizer preserving alphanumeric identifiers, tickers, and Vietnamese words."""
    normalized = _strip_vietnamese_accents((text or "").lower())
    return re.findall(r"[a-z0-9]+", normalized)


def parse_markdown_frontmatter(raw_content: str) -> tuple[dict[str, str], str]:
    """Splits optional YAML-like `---` frontmatter from Markdown body without external YAML deps."""
    text = (raw_content or "").replace("\r\n", "\n").lstrip("\ufeff")
    if not text.startswith("---\n"):
        return {}, text
    end_idx = text.find("\n---", 4)
    if end_idx == -1:
        return {}, text

    header_block = text[4:end_idx]
    body = text[end_idx + 4:].lstrip("\n")
    meta: dict[str, str] = {}
    for line in header_block.splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        key = k.strip().lower()
        val = v.strip().strip('"').strip("'")
        if key and val:
            meta[key] = val
    return meta, body


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
    """Local embedding provider: uses loopback Ollama embeddings when configured & reachable, otherwise deterministic lexical vectors."""

    def __init__(self, model_name: str | None = None, *, enable_ollama_http: bool | None = None):
        self.model_name = model_name or os.getenv("OLLAMA_EMBEDDING_MODEL") or os.getenv("EMBEDDING_MODEL") or "NOT_CONFIGURED"
        self.status = "NOT_CONFIGURED" if self.model_name in {None, "", "NOT_CONFIGURED"} else "CONFIGURED"
        self.enable_ollama_http = (
            enable_ollama_http
            if enable_ollama_http is not None
            else os.getenv("OLLAMA_EMBEDDING_HTTP", "1").strip().lower() in {"1", "true", "yes"}
        )
        self._last_backend = "NOT_CONFIGURED" if self.status == "NOT_CONFIGURED" else "lexical-hash-vector"
        self._cache: dict[str, list[float]] = {}

    def _try_ollama_embed(self, text: str) -> list[float] | None:
        if not self.enable_ollama_http or "PYTEST_CURRENT_TEST" in os.environ:
            return None
        try:
            import urllib.request

            from services.ai.config import OllamaConfig

            cfg = OllamaConfig.from_env()
            payload = json.dumps({"model": self.model_name, "prompt": text[:4000]}).encode("utf-8")
            req = urllib.request.Request(
                f"{cfg.base_url}/api/embeddings",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            vec = data.get("embedding")
            if isinstance(vec, list) and len(vec) >= 16:
                self._last_backend = "ollama-loopback"
                return [float(x) for x in vec]
        except Exception:
            return None
        return None

    def embed(self, text: str) -> list[float]:
        if self.status == "NOT_CONFIGURED":
            raise RuntimeError("EMBEDDING_PROVIDER = NOT_CONFIGURED")

        cache_key = hashlib.sha256((f"{self.model_name}:{text}").encode("utf-8")).hexdigest()
        if cache_key in self._cache:
            return list(self._cache[cache_key])

        ollama_vec = self._try_ollama_embed(text)
        if ollama_vec is not None:
            self._cache[cache_key] = ollama_vec
            return list(ollama_vec)

        self._last_backend = "lexical-hash-vector"
        tokens = _tokenize_rag(text)
        if not tokens:
            return [0.0] * 32

        counts = Counter(tokens)
        vector = [0.0] * 32
        for token, count in sorted(counts.items()):
            token_hash = int(hashlib.md5(token.encode("utf-8")).hexdigest()[:8], 16)
            slot = token_hash % 32
            weight = (1.0 + math.log1p(count)) * (1.0 + (token_hash % 1000) / 1000.0)
            vector[slot] += weight
        norm = math.sqrt(sum(v * v for v in vector))
        if norm > 0:
            vector = [round(v / norm, 6) for v in vector]
        self._cache[cache_key] = vector
        return list(vector)

    def describe(self) -> dict[str, Any]:
        return {
            "provider": "local-feature-vector",
            "status": self.status,
            "model": self.model_name if self.status == "CONFIGURED" else "NOT_CONFIGURED",
            "backend": self._last_backend,
            "note": "No paid embedding API is used. If no local model is configured, retrieval uses deterministic BM25 and the dense provider remains NOT_CONFIGURED.",
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
    """Local Hybrid RAG vector store supporting BM25 lexical scoring + optional dense cosine similarity fused via RRF."""

    BM25_K1 = 1.5
    BM25_B = 0.75
    RRF_K = 60

    def __init__(self, session: Session | None = None, embedding_provider: LocalEmbeddingProvider | None = None):
        self.session = session or SessionLocal()
        self.embedding_provider = embedding_provider or LocalEmbeddingProvider()

    def _document_filter(self, stmt, *, ticker=None, company=None, source=None, document_type=None, language=None, as_of_date=None):
        if ticker:
            tickers = [t.strip().upper() for t in str(ticker).split(",") if t.strip()]
            if len(tickers) == 1:
                stmt = stmt.filter(Document.ticker == tickers[0])
            elif len(tickers) > 1:
                stmt = stmt.filter(Document.ticker.in_(tickers))
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

    def _normalize_inline(self, text: str) -> str:
        return re.sub(r"[ \t]+", " ", (text or "")).strip()

    def _chunk_document(self, document: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Structural Markdown & paragraph chunker:
        - Tracks Markdown (`#`, `##`, `###`) and Roman/numbered headings into `section`.
        - Keeps Markdown pipe tables (`| ... |`) intact as `chunk_type='table'`.
        - Tracks line-range `page_reference` when explicit page numbers are absent.
        """
        raw_content = (document.get("raw_text") or "").replace("\r\n", "\n").strip()
        if not raw_content:
            return []

        explicit_page = document.get("page_reference") or None
        base_meta = {
            "source": document.get("source"),
            "document_type": document.get("document_type"),
            "title": document.get("title"),
        }

        lines = raw_content.splitlines()
        current_section = "Tong quan"
        chunks: list[dict[str, Any]] = []

        def _append_chunk(text_val: str, start_ln: int, end_ln: int, chunk_type: str = "prose") -> None:
            cleaned = text_val.strip()
            if not cleaned:
                return
            if chunk_type != "table":
                cleaned = re.sub(r"\s+", " ", cleaned).strip()
            if len(cleaned) > 1200:
                cleaned = cleaned[:1200]
            chunks.append({
                "chunk_index": len(chunks),
                "section": current_section,
                "page_reference": explicit_page or f"L{start_ln}-L{end_ln}",
                "text": cleaned,
                "metadata": {
                    **base_meta,
                    "chunk_type": chunk_type,
                    "start_line": start_ln,
                    "end_line": end_ln,
                },
            })

        i = 0
        total_lines = len(lines)
        while i < total_lines:
            raw_line = lines[i]
            stripped = raw_line.strip()
            if not stripped:
                i += 1
                continue

            # Detect Markdown headings (#, ##, ###) or Roman section headers (I., II., III.)
            md_heading = re.match(r"^(#{1,4})\s+(.+)$", stripped)
            roman_heading = re.match(r"^([IVX]{1,5}\.\s+.+)$", stripped)
            if md_heading:
                current_section = md_heading.group(2).strip()[:120]
                i += 1
                continue
            if roman_heading and len(stripped) <= 120:
                current_section = roman_heading.group(1).strip()
                i += 1
                continue

            # Detect Markdown table block and split oversized tables on row boundaries preserving headers
            if stripped.startswith("|") and "|" in stripped[1:]:
                t_start = i + 1
                table_lines = [stripped]
                i += 1
                while i < total_lines and lines[i].strip().startswith("|"):
                    table_lines.append(lines[i].strip())
                    i += 1
                is_sep_row = len(table_lines) >= 2 and bool(
                    re.match(r"^\|?[\s:-]+(?:\|[\s:-]+)+\|?$", table_lines[1])
                )
                full_text = "\n".join(table_lines)
                if len(full_text) <= 1200:
                    _append_chunk(full_text, t_start, i, chunk_type="table")
                elif is_sep_row and len(table_lines) > 2:
                    header_lines = table_lines[:2]
                    cur_rows: list[str] = []
                    block_start_offset = 2
                    for row_idx, row_line in enumerate(table_lines[2:], start=2):
                        candidate_lines = header_lines + cur_rows + [row_line]
                        candidate_text = "\n".join(candidate_lines)
                        if cur_rows and len(candidate_text) > 1200:
                            chunk_start_ln = t_start if block_start_offset == 2 else (t_start + block_start_offset)
                            chunk_end_ln = t_start + row_idx - 1
                            _append_chunk("\n".join(header_lines + cur_rows), chunk_start_ln, chunk_end_ln, chunk_type="table")
                            cur_rows = [row_line]
                            block_start_offset = row_idx
                        else:
                            cur_rows.append(row_line)
                    if cur_rows:
                        chunk_start_ln = t_start if block_start_offset == 2 else (t_start + block_start_offset)
                        _append_chunk("\n".join(header_lines + cur_rows), chunk_start_ln, i, chunk_type="table")
                else:
                    # Table without a standard Markdown separator row: split evenly at line boundaries
                    cur_lines: list[str] = []
                    cur_start_ln = t_start
                    for row_idx, row_line in enumerate(table_lines):
                        if cur_lines and len("\n".join(cur_lines + [row_line])) > 1200:
                            _append_chunk("\n".join(cur_lines), cur_start_ln, t_start + row_idx - 1, chunk_type="table")
                            cur_lines = [row_line]
                            cur_start_ln = t_start + row_idx
                        else:
                            cur_lines.append(row_line)
                    if cur_lines:
                        _append_chunk("\n".join(cur_lines), cur_start_ln, i, chunk_type="table")
                continue

            # Accumulate prose paragraph until blank line, heading, or table
            p_start = i + 1
            para_lines = [self._normalize_inline(stripped)]
            i += 1
            while i < total_lines:
                nxt = lines[i].strip()
                if not nxt:
                    break
                if re.match(r"^(#{1,4})\s+", nxt) or re.match(r"^[IVX]{1,5}\.\s+.+$", nxt) or (nxt.startswith("|") and "|" in nxt[1:]):
                    break
                para_lines.append(self._normalize_inline(nxt))
                i += 1
            p_end = i
            para_text = " ".join(para_lines).strip()

            if len(para_text) <= 450:
                _append_chunk(para_text, p_start, p_end, chunk_type="prose")
            else:
                sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", para_text) if part.strip()]
                if len(sentences) <= 1:
                    for offset in range(0, len(para_text), 400):
                        _append_chunk(para_text[offset:offset + 400], p_start, p_end, chunk_type="prose")
                else:
                    buf = ""
                    for sent in sentences:
                        candidate = f"{buf} {sent}".strip() if buf else sent
                        if len(candidate) <= 450:
                            buf = candidate
                        else:
                            if buf:
                                _append_chunk(buf, p_start, p_end, chunk_type="prose")
                            buf = sent
                    if buf:
                        _append_chunk(buf, p_start, p_end, chunk_type="prose")

        return chunks

    def index_documents(self, documents: list[dict[str, Any]]) -> list[str]:
        ids: list[str] = []
        for document in documents:
            document_id = str(
                document.get("document_id")
                or document.get("id")
                or hashlib.sha256(json.dumps(document.get("metadata", {}), sort_keys=True).encode("utf-8")).hexdigest()[:12]
            )
            checksum = document.get("checksum") or hashlib.sha256((document.get("raw_text") or "").encode("utf-8")).hexdigest()
            ticker_norm = (document.get("ticker") or "").upper()
            is_synth = bool(document.get("is_synthetic"))
            existing = self.session.query(Document).filter(Document.document_id == document_id).first()
            if existing is None and not is_synth and checksum:
                dup = (
                    self.session.query(Document)
                    .filter(
                        Document.ticker == ticker_norm,
                        Document.checksum == checksum,
                        Document.is_synthetic.is_(False),
                    )
                    .first()
                )
                if dup is not None:
                    dup_chunks = self.session.query(DocumentChunk).filter(DocumentChunk.document_id == dup.document_id).count()
                    if dup_chunks > 0:
                        ids.append(dup.document_id)
                        continue
                    existing = dup
                    document_id = dup.document_id
            if existing is None:
                record = Document(
                    document_id=document_id,
                    ticker=ticker_norm,
                    company=document.get("company"),
                    source=document.get("source") or "LOCAL_DOCUMENT",
                    publication_date=document.get("publication_date"),
                    period=document.get("period"),
                    document_type=document.get("document_type"),
                    language=document.get("language") or "en",
                    version=str(document.get("version") or "1"),
                    checksum=checksum,
                    title=document.get("title"),
                    raw_text=document.get("raw_text") or "",
                    status=document.get("status") or "READY",
                    is_synthetic=is_synth,
                    metadata_json=document.get("metadata") or {},
                )
                self.session.add(record)
                self.session.flush()
            else:
                record = existing
                existing_chunk_count = self.session.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).count()
                if record.checksum == checksum and existing_chunk_count > 0:
                    ids.append(document_id)
                    continue
                record.ticker = (document.get("ticker") or record.ticker or "").upper()
                record.company = document.get("company") or record.company
                record.source = document.get("source") or record.source
                record.publication_date = document.get("publication_date") or record.publication_date
                record.period = document.get("period") or record.period
                record.document_type = document.get("document_type") or record.document_type
                record.title = document.get("title") or record.title
                record.raw_text = document.get("raw_text") or record.raw_text
                record.checksum = checksum
                record.is_synthetic = bool(document.get("is_synthetic"))
                record.metadata_json = document.get("metadata") or record.metadata_json
                self.session.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).delete()

            document_chunks = self._chunk_document(document)
            for chunk in document_chunks:
                chunk_text = chunk["text"]
                embed_input = f"{chunk.get('section') or ''}\n{chunk_text}".strip()
                try:
                    embedding = self.embedding_provider.embed(embed_input)
                    embedding_model = self.embedding_provider.model_name
                    embedding_version = f"{self.embedding_provider._last_backend}-v2"
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

            if self.session.in_nested_transaction():
                self.session.flush()
            else:
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
        chunk_tokens = set(_tokenize_rag(chunk_text))
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

        q_token_list = _tokenize_rag(query)
        q_tokens = set(q_token_list)
        if not q_tokens:
            return []

        dense_active = False
        query_vector: list[float] = [0.0] * 32
        try:
            query_vector = self.embedding_provider.embed(query)
            dense_active = any(abs(v) > 1e-9 for v in query_vector)
        except RuntimeError:
            dense_active = False

        stmt = select(DocumentChunk).join(Document)
        stmt = self._document_filter(
            stmt,
            ticker=ticker,
            company=company,
            source=source,
            document_type=document_type,
            language=language,
            as_of_date=as_of_date,
        )

        rows = self.session.execute(stmt).scalars().all()
        if not rows:
            return []

        doc_ids = {r.document_id for r in rows}
        docs_by_id = {
            d.document_id: d
            for d in self.session.query(Document).filter(Document.document_id.in_(doc_ids)).all()
        }

        # Precompute BM25 statistics across filtered PIT chunks
        tokenized_chunks: list[tuple[DocumentChunk, Document, list[str], Counter[str], set[str]]] = []
        df_counts: Counter[str] = Counter()
        total_dl = 0

        for row in rows:
            doc = docs_by_id.get(row.document_id)
            if doc is None:
                continue
            combined_text = f"{row.section or ''} {doc.title or ''} {row.text or ''}"
            c_tokens = _tokenize_rag(combined_text)
            section_tokens = set(_tokenize_rag(f"{row.section or ''} {doc.title or ''}"))
            tf = Counter(c_tokens)
            total_dl += max(1, len(c_tokens))
            for tok in tf.keys():
                df_counts[tok] += 1
            tokenized_chunks.append((row, doc, c_tokens, tf, section_tokens))

        num_docs = len(tokenized_chunks)
        if num_docs == 0:
            return []
        avgdl = max(1.0, total_dl / num_docs)

        candidates: list[dict[str, Any]] = []
        has_dense_vectors = False

        for row, doc, c_tokens, tf, section_tokens in tokenized_chunks:
            dl = max(1, len(c_tokens))
            bm25_score = 0.0
            for q_tok in q_tokens:
                freq = tf.get(q_tok, 0)
                if freq <= 0:
                    continue
                df = df_counts.get(q_tok, 0)
                idf = math.log((num_docs - df + 0.5) / (df + 0.5) + 1.0)
                denom = freq + self.BM25_K1 * (1.0 - self.BM25_B + self.BM25_B * (dl / avgdl))
                bm25_score += idf * ((freq * (self.BM25_K1 + 1.0)) / max(1e-9, denom))
                if q_tok in section_tokens:
                    bm25_score += 0.25 * idf

            dense_score = 0.0
            row_emb = row.embedding or []
            if dense_active and row_emb and len(row_emb) == len(query_vector) and any(abs(v) > 1e-9 for v in row_emb):
                has_dense_vectors = True
                dense_score = max(0.0, self._cosine_similarity(query_vector, row_emb))

            candidates.append({
                "row": row,
                "doc": doc,
                "bm25_score": bm25_score,
                "dense_score": dense_score,
            })

        retrieval_mode = "HYBRID_BM25_DENSE" if (dense_active and has_dense_vectors) else "BM25_LEXICAL_ONLY"

        # Assign dense & BM25 ranks for deterministic Reciprocal Rank Fusion
        bm25_ranked = sorted(
            [c for c in candidates if c["bm25_score"] > 0],
            key=lambda x: (-x["bm25_score"], x["row"].document_id, x["row"].chunk_id),
        )
        bm25_rank_map = {c["row"].chunk_id: idx for idx, c in enumerate(bm25_ranked, start=1)}

        dense_rank_map: dict[str, int] = {}
        if retrieval_mode == "HYBRID_BM25_DENSE":
            dense_ranked = sorted(
                [c for c in candidates if c["dense_score"] > 0.10],
                key=lambda x: (-x["dense_score"], x["row"].document_id, x["row"].chunk_id),
            )
            dense_rank_map = {c["row"].chunk_id: idx for idx, c in enumerate(dense_ranked, start=1)}

        scored: list[dict[str, Any]] = []
        for cand in candidates:
            row = cand["row"]
            doc = cand["doc"]
            bm25_val = cand["bm25_score"]
            dense_val = cand["dense_score"]
            b_rank = bm25_rank_map.get(row.chunk_id)
            d_rank = dense_rank_map.get(row.chunk_id)

            if retrieval_mode == "HYBRID_BM25_DENSE":
                if b_rank is None and d_rank is None:
                    continue
                rrf = (1.0 / (self.RRF_K + b_rank) if b_rank is not None else 0.0) + (
                    1.0 / (self.RRF_K + d_rank) if d_rank is not None else 0.0
                )
                # Preserve strict magnitude order as tiny deterministic tiebreaker
                final_score = rrf + min(bm25_val, 50.0) * 1e-4 + dense_val * 1e-3
            else:
                if bm25_val <= 0:
                    continue
                final_score = bm25_val

            meta = row.metadata_json or {}
            scored.append({
                "citation_id": row.chunk_id,
                "document_id": row.document_id,
                "chunk_id": row.chunk_id,
                "text": row.text,
                "score": round(final_score, 6),
                "bm25_score": round(bm25_val, 6),
                "dense_score": round(dense_val, 6),
                "retrieval_mode": retrieval_mode,
                "source": doc.source,
                "publication_date": doc.publication_date.isoformat() if doc.publication_date else None,
                "ticker": doc.ticker,
                "company": doc.company,
                "title": doc.title,
                "period": doc.period,
                "document_type": doc.document_type,
                "language": doc.language,
                "section": row.section,
                "page_reference": row.page_reference,
                "chunk_type": meta.get("chunk_type", "prose"),
                "is_synthetic": bool(doc.is_synthetic),
                "metadata": meta,
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
        fixtures = self._synthetic_documents()
        fixture_ids = [doc["document_id"] for doc in fixtures]
        existing_ids = {
            row[0]
            for row in self.session.query(Document.document_id)
            .filter(Document.document_id.in_(fixture_ids))
            .all()
        }
        missing = [doc for doc in fixtures if doc["document_id"] not in existing_ids]
        if missing:
            self.vector_store.index_documents(missing)
        return fixture_ids

    def ingest_local_directory(self, directory: str | Path = "data/documents") -> list[str]:
        """Indexes real local filings/reports with YAML frontmatter from `directory` into Document/DocumentChunk."""
        dir_path = Path(directory)
        if not dir_path.exists() or not dir_path.is_dir():
            return []

        docs_to_index: list[dict[str, Any]] = []
        for file_path in sorted(dir_path.iterdir()):
            if not file_path.is_file() or file_path.suffix.lower() not in {".txt", ".md"}:
                continue
            raw_content = file_path.read_text(encoding="utf-8", errors="replace")
            meta, body = parse_markdown_frontmatter(raw_content)
            if not body.strip():
                continue

            parts = file_path.stem.split("_")
            ticker = (meta.get("ticker") or (parts[0] if parts else "")).strip().upper()
            pub_date_obj: date | None = None
            raw_pub = meta.get("publication_date")
            if raw_pub:
                try:
                    pub_date_obj = date.fromisoformat(raw_pub[:10])
                except ValueError:
                    pub_date_obj = None
            if pub_date_obj is None:
                for token in parts:
                    if re.match(r"^\d{4}-\d{2}-\d{2}$", token):
                        try:
                            pub_date_obj = date.fromisoformat(token)
                            break
                        except ValueError:
                            pass

            body_checksum = hashlib.sha256(body.encode("utf-8")).hexdigest()
            existing_doc = (
                self.session.query(Document)
                .filter(
                    Document.ticker == ticker,
                    Document.checksum == body_checksum,
                    Document.is_synthetic.is_(False),
                )
                .first()
            )
            doc_id = existing_doc.document_id if existing_doc else file_path.stem

            docs_to_index.append({
                "document_id": doc_id,
                "checksum": body_checksum,
                "ticker": ticker,
                "company": meta.get("company") or ticker,
                "source": meta.get("source") or "LOCAL_CORPUS_FILING",
                "publication_date": pub_date_obj,
                "period": meta.get("period"),
                "document_type": meta.get("document_type") or "CORPORATE_FILING",
                "language": meta.get("language") or "vi",
                "version": meta.get("version") or "1",
                "title": meta.get("title") or file_path.stem.replace("_", " "),
                "raw_text": body,
                "status": "READY",
                "is_synthetic": False,
                "metadata": {
                    "filename": file_path.name,
                    "source_notes": meta.get("source") or "LOCAL_CORPUS_FILING",
                    "document_kind": "official-local-filing",
                },
            })

        if not docs_to_index:
            return []
        return self.vector_store.index_documents(docs_to_index)

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
        auto_ingest_local: bool = False,
    ) -> dict[str, Any]:
        if auto_ingest_local:
            self.ingest_local_directory()
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
        retrieval_mode = hits[0]["retrieval_mode"] if hits else (
            "HYBRID_BM25_DENSE" if self.vector_store.embedding_provider.status == "CONFIGURED" else "BM25_LEXICAL_ONLY"
        )
        return {
            "status": "AVAILABLE" if hits else "INSUFFICIENT_DATA",
            "retrieval_mode": retrieval_mode,
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
    "parse_markdown_frontmatter",
]
