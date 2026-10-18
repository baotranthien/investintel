"""
RAG Document Ingestion Pipeline.

Scans the `data/documents/` directory for text/markdown/PDF filings, extracts text and metadata,
chunks documents, and indexes them into the canonical RAG database:
- `documents` table
- `document_chunks` table (with citations, page references, sections)

Enforces strict Point-In-Time (PIT) integrity:
Every indexed document MUST have a verified `publication_date`.
Queries with `as_of_date` will strictly exclude any chunk with `publication_date > as_of_date`.

File Naming Conventions or Frontmatter:
1. Filename pattern: `[TICKER]_[DOC_TYPE]_[YYYY-MM-DD]_[TITLE].[ext]`
   Example: `FPT_ANNUAL_REPORT_2024-04-10_BaoCaoThuongNien2023.txt`
   or `VCB_SHAREHOLDER_MEETING_2024-04-27_NghiQuyetDHCDBienBan.txt`
2. Optional YAML/JSON frontmatter at the beginning of the file:
   ---
   ticker: FPT
   company: Cong ty Co phan FPT
   publication_date: 2024-04-10
   document_type: ANNUAL_REPORT
   source: HOSE_OFFICIAL_DISCLOSURE
   period: FY2023
   language: vi
   ---
"""
import sys
import os
import re
import json
import hashlib
import argparse
import logging
from datetime import datetime, date

# Ensure project root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database.connection import SessionLocal
from database.models import Document, DocumentChunk
from services.research.rag import DocumentRAGService, LocalVectorStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ingest_rag")

DOCUMENTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "documents"))


def parse_frontmatter(content: str) -> tuple[dict, str]:
    """Extracts frontmatter metadata from top of text if present."""
    metadata = {}
    body = content
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)
    if match:
        raw_meta, body = match.group(1), match.group(2)
        for line in raw_meta.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                k = k.strip().lower()
                v = v.strip().strip('"').strip("'")
                metadata[k] = v
    return metadata, body.strip()


def parse_filename_metadata(filename: str) -> dict:
    """Parses metadata from standardized filename: TICKER_DOCTYPE_YYYY-MM-DD_TITLE.ext"""
    meta = {}
    base_name = os.path.splitext(filename)[0]
    parts = base_name.split("_")
    if len(parts) >= 3:
        meta["ticker"] = parts[0].upper()
        meta["document_type"] = parts[1].upper()
        try:
            meta["publication_date"] = datetime.strptime(parts[2], "%Y-%m-%d").date()
        except ValueError:
            pass
        if len(parts) >= 4:
            meta["title"] = " ".join(parts[3:])
    return meta


def extract_text_from_file(filepath: str) -> str:
    """Extracts text content from .txt, .md, or .pdf files."""
    ext = os.path.splitext(filepath)[1].lower()
    if ext in (".txt", ".md", ".json"):
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    elif ext == ".pdf":
        try:
            import pypdf
            reader = pypdf.PdfReader(filepath)
            text_parts = []
            for i, page in enumerate(reader.pages):
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(f"\n[Page {i+1}]\n" + page_text)
            return "\n".join(text_parts)
        except ImportError:
            logger.warning(f"pypdf not installed. Reading {filepath} as raw binary fallback.")
            with open(filepath, "rb") as f:
                return f.read().decode("utf-8", errors="replace")
    return ""


def ingest_documents_from_directory(dir_path: str = DOCUMENTS_DIR) -> dict:
    """Scans directory and indexes all documents into the RAG VectorStore."""
    if not os.path.exists(dir_path):
        os.makedirs(dir_path, exist_ok=True)
        logger.info(f"Created documents directory: {dir_path}")

    files = [f for f in os.listdir(dir_path) if os.path.isfile(os.path.join(dir_path, f))]
    logger.info(f"Found {len(files)} files in {dir_path}")

    session = SessionLocal()
    vector_store = LocalVectorStore(session=session)
    ingested_count = 0
    total_chunks = 0
    results = []

    try:
        for fname in sorted(files):
            fpath = os.path.join(dir_path, fname)
            raw_content = extract_text_from_file(fpath)
            if not raw_content or not raw_content.strip():
                logger.warning(f"Skipping empty file: {fname}")
                continue

            front_meta, body_text = parse_frontmatter(raw_content)
            fn_meta = parse_filename_metadata(fname)

            # Resolve ticker
            ticker = (front_meta.get("ticker") or fn_meta.get("ticker") or "GENERAL").upper()
            
            # Resolve publication date (CRITICAL FOR POINT-IN-TIME)
            pub_date = None
            raw_pub_date = front_meta.get("publication_date") or fn_meta.get("publication_date")
            if isinstance(raw_pub_date, date):
                pub_date = raw_pub_date
            elif isinstance(raw_pub_date, str):
                try:
                    pub_date = datetime.strptime(raw_pub_date[:10], "%Y-%m-%d").date()
                except ValueError:
                    pass
            if pub_date is None:
                # Default to file modification date as conservative fallback
                mtime = os.path.getmtime(fpath)
                pub_date = datetime.fromtimestamp(mtime).date()
                logger.warning(f"[{fname}] Missing publication_date; using file timestamp {pub_date}")

            doc_type = front_meta.get("document_type") or fn_meta.get("document_type") or "RESEARCH_REPORT"
            company = front_meta.get("company") or f"{ticker} Company"
            source = front_meta.get("source") or "INTERNAL_RESEARCH_CORPUS"
            period = front_meta.get("period") or str(pub_date.year)
            language = front_meta.get("language") or "vi"
            title = front_meta.get("title") or fn_meta.get("title") or os.path.splitext(fname)[0]

            # Generate deterministic document_id based on ticker, doc_type, pub_date, and file hash
            file_hash = hashlib.sha256(raw_content.encode("utf-8")).hexdigest()[:8]
            doc_id = f"{ticker}-{doc_type}-{pub_date.isoformat()}-{file_hash}"

            doc_payload = {
                "document_id": doc_id,
                "ticker": ticker,
                "company": company,
                "source": source,
                "publication_date": pub_date,
                "period": period,
                "document_type": doc_type,
                "language": language,
                "version": "1",
                "title": title,
                "raw_text": body_text,
                "status": "READY",
                "is_synthetic": False,
                "metadata": {
                    "filename": fname,
                    "filepath": fpath,
                    "checksum": hashlib.sha256(raw_content.encode("utf-8")).hexdigest(),
                    "file_size": len(raw_content)
                }
            }

            indexed_ids = vector_store.index_documents([doc_payload])
            chunks_count = session.query(DocumentChunk).filter(DocumentChunk.document_id == doc_id).count()
            total_chunks += chunks_count
            ingested_count += 1
            logger.info(f"[INDEXED] {fname} -> doc_id={doc_id}, chunks={chunks_count}, pub_date={pub_date}")
            results.append({
                "filename": fname,
                "document_id": doc_id,
                "ticker": ticker,
                "publication_date": pub_date.isoformat(),
                "chunks": chunks_count
            })

    finally:
        session.close()

    return {
        "status": "SUCCESS" if ingested_count > 0 else "NO_FILES",
        "documents_ingested": ingested_count,
        "total_chunks": total_chunks,
        "results": results
    }


def main():
    parser = argparse.ArgumentParser(description="Ingest research documents and corporate filings for RAG")
    parser.add_argument("--dir", type=str, default=DOCUMENTS_DIR, help="Path to documents folder")
    parser.add_argument("--query", type=str, default=None, help="Optional test retrieval query after ingestion")
    parser.add_argument("--ticker", type=str, default=None, help="Optional ticker filter for test query")
    parser.add_argument("--as-of", type=str, default=None, help="Optional as_of_date (YYYY-MM-DD) for PIT query test")
    args = parser.parse_args()

    ingest_res = ingest_documents_from_directory(args.dir)
    logger.info(f"Ingestion complete: {ingest_res['documents_ingested']} documents, {ingest_res['total_chunks']} chunks.")

    # Run optional test retrieval
    if args.query:
        as_of_dt = datetime.strptime(args.as_of, "%Y-%m-%d").date() if args.as_of else None
        rag_service = DocumentRAGService()
        res = rag_service.retrieve_documents(
            args.query,
            ticker=args.ticker,
            as_of_date=as_of_dt,
            limit=3
        )
        logger.info(f"Test Retrieval for '{args.query}' (as_of={as_of_dt}): {res['count']} hits found.")
        for d in res["documents"]:
            logger.info(f"  Hit: [{d['ticker']}] {d['citation_id']} (pub: {d['publication_date']}) - Score: {d['score']}")
            logger.info(f"  Snippet: {d['text'][:150]}...")


if __name__ == "__main__":
    main()
