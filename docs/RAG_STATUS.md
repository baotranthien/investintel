# RAG Status Report

## Scope
This report covers the local 6G document intelligence implementation. The goal is to validate the document pipeline, local retrieval, temporal filtering, and citation mapping without claiming PostgreSQL or production integration.

## Current Local Status
- 6G local implementation: COMPLETE for local development and contract validation
- PostgreSQL production verification: BLOCKED
- Live HOSE / live external document pipeline: BLOCKED
- Embedding model: CONFIGURED only when an explicit local embedding model is set; otherwise reported as NOT_CONFIGURED
- Vector store: Local SQLite-backed vector store implemented; pgvector compatibility layer remains ready for future PostgreSQL deployment

## Document Pipeline
The local pipeline follows the intended sequence:

Document
→ Parse
→ Normalize
→ Metadata
→ Chunk
→ Embed
→ Store
→ Retrieve
→ Evidence / Citation
→ AI Context

Implementation details:
- Document registry stored in `database/models.py`
- Chunk storage stored in `database/models.py`
- Retrieval logic stored in `services/research/rag.py`
- AI tool integration exposed through `services/ai/tools.py`

## Storage Architecture
- `VectorStore`: abstraction interface for retrieval backends
- `LocalVectorStore`: local SQLite-backed deterministic retrieval implementation
- `PGVectorStore`: compatibility placeholder for future PostgreSQL / pgvector deployment

Important:
- PostgreSQL is not treated as verified here.
- Local development continues without fabricating PostgreSQL success.

## Embedding State
- Default behavior: local vector store runs with a stable lexical feature vector when no embedding model is configured
- If no embedding model is explicitly configured, the provider status is explicitly `NOT_CONFIGURED`
- There is no paid API integration and no fabricated embedding output

## Document Metadata
Minimum metadata is preserved where available:
- document_id
- ticker
- company
- source
- publication_date
- period
- document_type
- language
- version
- checksum

When a source is absent, the document is clearly labeled as a synthetic local fixture and not presented as an official source document.

## Chunking Rules
- The document is normalized and split into paragraph / section-sized chunks
- Metadata includes section, page reference, source, and document kind
- Duplicate chunk IDs are prevented by using deterministic document/chunk identifiers
- Re-ingestion does not create duplicates because the document_id and chunk_id pair is unique

## Temporal Retrieval
Temporal filtering is enforced before context is returned to the AI layer.

Logic:
- retrieval is filtered by `publication_date <= as_of_date`
- future documents are excluded before ranking and AI context generation
- same query with earlier and later as_of dates yields different result sets by design

Local validation included:
- document A published 2023-05-01
- document B published 2023-09-01
- query as_of=2023-06-01 returns only A
- query as_of=2023-10-01 returns A and B

## Retrieval Results
The retrieval contract includes:
- chunk_id
- document_id
- text/snippet
- score
- source
- publication date
- ticker
- company
- metadata

## Citation / Evidence
Each chunk carries a deterministic citation identifier that points to a real stored chunk. The citation is not fabricated and is only valid if it maps to a real stored document/chunk and temporal constraints are satisfied.

## AI Integration
The local retrieval layer is connected to the AI tool context through `AITools.get_context()`. When retrieval is empty, the status is explicitly `INSUFFICIENT_DATA` and the AI is not forced to invent evidence.

## Local Validation Summary
- retrieval tests: PASS
- temporal filtering tests: PASS
- citation mapping tests: PASS
- empty retrieval handling: PASS
- determinism checks: PASS

## Benchmark Notes
- Local test corpus: synthetic fixture documents only
- vector store: SQLite-backed local store
- embedding provider: local feature-vector or explicit NOT_CONFIGURED state
- no claim of real production RAG quality is made

## Known Limitations
- PostgreSQL is unavailable for live verification
- live HOSE / market document feed is not connected
- no real official annual report ingestion is active in this environment
- any vector store results are local-development grade, not production-grade evidence

## Production Status
This is local 6G acceptance, not production PostgreSQL acceptance.

## Next Milestone
6H — Analyst Automation
