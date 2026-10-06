# FinResearch — Interview Guide

This document explains every part of the system in plain English so you can answer technical interview questions confidently. Each answer connects to the actual code in the repository.

---

## General System Questions

**1. What problem does FinResearch solve?**

Financial analysts spend large amounts of time reading SEC filings — 10-Ks and 10-Qs that can run hundreds of pages. The specific information they need (risk factors, revenue trends, management commentary on competition) is buried in dense text. FinResearch lets you ask a natural-language question and get a grounded answer backed by the actual filing text, with clickable citations to the original source. The key constraint is that citations must come from the database, not the model's imagination — that's the hard part.

**2. Walk me through the architecture.**

There are five layers:

1. **Ingestion**: We fetch filing metadata from SEC EDGAR's API, download the actual HTML document, parse it to extract clean text, detect section boundaries, chunk it into ~512-token segments, embed each chunk with a sentence-transformer model, and store everything in PostgreSQL.

2. **Storage**: Three tables — `companies`, `filings`, and `document_chunks`. The chunks table includes the text, section name, filing metadata as JSONB, and a 384-dimensional vector (the embedding) stored via pgvector.

3. **Retrieval**: Two search legs — vector (cosine similarity via pgvector) and keyword (PostgreSQL full-text search with `ts_rank`). We fuse them using Reciprocal Rank Fusion to get a single ranked list. An optional cross-encoder reranker can refine the top results.

4. **RAG**: Retrieved chunks become numbered context excerpts in a prompt. The LLM is instructed to cite by number. After generation, citations are constructed from the actual chunk metadata — not from what the model wrote.

5. **API/Frontend**: FastAPI exposes `/search` and `/ask` endpoints. Streamlit provides a usable frontend.

**3. How does data ingestion work?**

See the detailed section at the bottom of this guide.

**4. Where does the data come from?**

SEC EDGAR — the public database of all required filings by US public companies. It's completely free and open. We use two API endpoints:
- `https://www.sec.gov/files/company_tickers.json` — maps ticker symbols to CIK numbers (the SEC's internal company identifiers)
- `https://data.sec.gov/submissions/CIK{cik}.json` — returns a company's full filing history with accession numbers, dates, and primary document names

We then construct the document URL as `https://www.sec.gov/Archives/edgar/data/{cik}/{accession_no_dashes}/{primary_document}` and download it directly.

**5. How do you prevent duplicate ingestion?**

The `filings` table has a UNIQUE constraint on `accession_number`. Before processing any filing, the pipeline queries for an existing row with that accession number. If one is found, the filing is skipped. This is enforced at both the application layer (check before processing) and the database layer (unique constraint prevents inserts). So if the script is run twice, or if the server crashes midway and restarts, no duplicates are created.

**6. What happens if SEC ingestion fails halfway through?**

Each filing is processed in a database transaction. If fetching, parsing, chunking, or embedding fails for a filing, the exception propagates, the session rolls back, and that filing is left unpersisted. The next run will retry it (since no row was committed). If multiple filings are being ingested in one run, a failure on one filing does NOT roll back the others — they were committed independently. The error is logged with the accession number so it can be investigated.

**7. How are filings parsed?**

`app/ingestion/parser.py`. Modern 10-K filings are HTML (or SGML wrapping HTML). We use BeautifulSoup with the lxml parser to extract text from the HTML. Specifically:
- Remove `<script>`, `<style>`, `<nav>`, `<header>`, `<footer>` tags
- Insert newlines around block elements (`<p>`, `<div>`, `<tr>`, etc.) to preserve structure
- Call `.get_text()` to get the raw text

After extraction, we run section detection: we search the lowercased text for patterns like `item\s+1[^a-zA-Z0-9]` (matches "Item 1." or "ITEM 1 ") and use match positions to slice the text into sections. Each section becomes its own chunk source.

**8. Why did you choose this chunking strategy?**

Three design choices:
1. **Token-aware**: We use tiktoken (cl100k_base, the GPT-4 tokenizer) to measure chunk size in tokens rather than characters. This matters because the LLM context window is measured in tokens.
2. **Section-aware**: If we detected sections, chunks stay within section boundaries. This means chunks are coherent units of information and can be attributed to a specific section (e.g., "Risk Factors").
3. **Overlap**: Adjacent chunks share `chunk_overlap` tokens (default 64). This prevents information at chunk boundaries from being missed.

Naive fixed-character splitting is simpler but ignores token counts and ignores document structure. The tradeoff is complexity — we need tiktoken and section detection to work correctly.

**9. What are embeddings?**

A dense vector representation of text where semantically similar texts have vectors close together in the vector space (measured by cosine similarity). We use `all-MiniLM-L6-v2` from sentence-transformers, which produces 384-dimensional vectors. The model was trained on a large corpus of sentence pairs to place semantically similar sentences near each other. When we embed a query and a chunk separately and compute cosine similarity, a high similarity means the chunk is likely relevant to the query — even if they share no exact words.

**10. Why pgvector?**

pgvector is a PostgreSQL extension that adds a `vector` column type and similarity operators (cosine distance `<=>`, L2 distance `<->`, inner product `<#>`). Instead of loading all vectors into Python and computing distances in NumPy, we push the computation into PostgreSQL where it runs efficiently against only the rows that pass our WHERE filters. This keeps the architecture simple (one database, not two) and avoids shipping embeddings over the network.

**11. Why PostgreSQL rather than a dedicated vector DB (Pinecone, Weaviate, Chroma)?**

Dedicated vector databases are optimized for ANN (approximate nearest neighbor) search at very large scale. For a corpus of thousands to low millions of chunks, PostgreSQL + pgvector is entirely adequate. The advantages of staying in PostgreSQL are: we don't need to manage two data stores, the relational data (companies, filings) and the vectors live in the same transactions, and we can filter by ticker/filing_type in SQL before doing vector search — which dedicated vector DBs handle with varying degrees of elegance.

**12. What is cosine similarity?**

For two vectors A and B, cosine similarity = (A · B) / (|A| × |B|). It measures the angle between the vectors rather than their magnitude. A similarity of 1.0 means identical direction (semantically identical), 0.0 means orthogonal (unrelated), -1.0 means opposite. We normalize embeddings to unit length before storing (`normalize_embeddings=True`), so cosine similarity and dot product become equivalent, and the pgvector `<=>` operator (cosine distance = 1 - cosine similarity) returns the right ranking.

**13. What is hybrid retrieval?**

We run two independent retrieval systems — vector search and keyword search — and merge their ranked result lists into a single list. Vector search captures semantic similarity (paraphrases, synonyms). Keyword search captures exact matches (ticker symbols, dollar amounts, specific regulatory terms). Neither alone covers the full space of user queries, so combining them improves recall.

**14. Why is vector search alone insufficient?**

Vector search can fail for:
- **Exact terminology**: "Item 1A" or "SFAS 142" or "CIK 320193" — terms that appear verbatim in the filing but whose embeddings don't cluster with the query
- **Numbers**: "$12.3 billion" or "3%" — embeddings don't encode numerical proximity well
- **Rare terms**: regulatory or technical jargon that appears infrequently in the embedding model's training corpus may not have strong semantic neighbors

Keyword search handles all of these correctly.

**15. What is Reciprocal Rank Fusion?**

RRF takes multiple ranked lists and merges them. For each document in each list, it computes `1 / (k + rank)` where k is a constant (we use 60, from the original paper) and rank is the document's position in that list (1-indexed). These scores are summed across lists. The document with the highest total RRF score is ranked first. Documents that appear in multiple lists get boosted. Documents that appear in only one list still contribute. The k constant dampens the impact of the top rank — without it, a document ranked #1 in one list would completely dominate.

**16. What is Recall@K?**

Recall@K = (number of relevant documents in top-K results) / (total number of relevant documents). It measures how many of the documents we actually care about we managed to find in the first K results. Recall@10 of 0.8 means we found 80% of the relevant documents in our top-10 retrieval results.

**17. What is MRR?**

Mean Reciprocal Rank = average of 1/rank_of_first_relevant_result across all queries. MRR of 0.5 means on average the first relevant document appeared at rank 2. MRR rewards systems that put the first relevant document near the top, regardless of how many relevant documents appear after it.

**18. Difference between Recall@K and MRR?**

Recall@K rewards finding *all* the relevant documents. MRR rewards finding *the first* relevant document quickly. For a use case where the user wants a single good answer, MRR matters more. For a use case where completeness matters (finding all evidence), Recall@K matters more. In RAG, we care about both — we want the right context to appear, but we also want it near the top so it's included in the LLM's prompt.

**19. How did you create the evaluation dataset?**

The built-in dataset is a small hand-crafted set of question/expected-section pairs. Each example specifies a question, a ticker, a filing type, and the section name(s) that should contain the relevant evidence. Retrieval is then evaluated by checking whether the section names of retrieved chunks match the expected sections. This is a section-level proxy for relevance — it's not perfect, but it's interpretable and reproducible. A production evaluation dataset would have chunk-level relevance labels collected through human annotation or LLM-assisted labeling.

**20. How are citations validated?**

`app/rag/citations.py`. We use a regex to extract all [N] markers from the answer, then check two things:
1. Is there at least one citation in the answer?
2. Are all cited indices in the range [1, len(context_chunks)]?

Citations themselves are constructed from the chunk metadata we retrieved — not from the model output. If the model says [1], we know exactly which chunk that is, who filed it, when, and what URL it lives at, because we numbered the context excerpts ourselves before building the prompt.

**21. What prevents hallucination?**

Several mechanisms:
1. The system prompt explicitly instructs the model to answer only from provided excerpts and to say when evidence is insufficient.
2. Citations are generated from retrieved metadata — the model cannot produce a source URL that doesn't exist in the database.
3. The context prompt numbers each excerpt and asks the model to cite by number — this creates a structured reference that can be validated.
4. If no relevant filings are found, the `answer_question` function returns an "no data" message before calling the LLM at all.

None of this is foolproof. An LLM can still confabulate within a response even with strong instructions. But citation grounding is the most important layer — it ensures that even if the answer text is imprecise, the cited sources are real.

**22. Why FastAPI?**

FastAPI gives us automatic request/response validation via Pydantic, auto-generated OpenAPI docs at `/docs`, type hints throughout (which are also documentation), and good async support if we ever need it. It's a good fit for a typed Python API that needs to be understandable quickly.

**23. Why Docker?**

Docker means anyone can run the system without installing PostgreSQL with pgvector manually. `docker compose up --build` brings up the database, API, and frontend with one command. The pgvector image (`pgvector/pgvector:pg16`) ships PostgreSQL 16 with the pgvector extension pre-installed, so we don't need to compile it.

**24. How would this architecture scale from 10 filings to 500,000 chunks?**

At 500K chunks, several things need attention:
- **Vector index**: By default pgvector does exact search (full scan). For large tables, we'd add an HNSW index (`CREATE INDEX ON document_chunks USING hnsw (embedding vector_cosine_ops)`) for approximate nearest-neighbor search. This trades a small amount of recall for dramatically faster queries.
- **Full-text index**: Add a GIN index on `to_tsvector('english', text)` for fast keyword search.
- **Embedding compute**: Batch embedding during ingestion is already implemented. At high volume, this could be parallelized across workers.
- **Connection pooling**: PgBouncer in front of PostgreSQL for connection pooling under load.
- **Read replicas**: The API only reads for search. A read replica handles search traffic while the write replica handles ingestion.

**25. What would break first at 10x scale?**

Probably the vector search latency — exact nearest-neighbor search scans every row. The fix is an HNSW index. The ingestion pipeline would also be slow at 10x scale because it's sequential — fixing that would require a task queue and parallel workers.

**26. How would you monitor this in production?**

- **`/health` endpoint** — database connectivity, latency of the health check itself
- **Ingestion metrics**: count of filings ingested per hour, failure rate, duration per filing
- **Retrieval latency**: p50/p95 latency for `/search` and `/ask`
- **LLM error rate**: track 429 (rate limit), 503 (unavailable), and empty responses
- **Chunk count over time**: monitoring that the corpus is growing as expected
- Standard infra: container CPU/memory, Postgres connection count, disk usage for the vector data

**27. What happens when the embedding model changes?**

The existing vectors are incompatible with a new model — cosine similarity across different embedding spaces is meaningless. The migration would require: (1) selecting a migration strategy (re-embed all chunks in a batch, or run a dual-index with both models temporarily), (2) running `embed_texts()` on all chunk texts in batches, (3) updating the `embedding` column with the new vectors, (4) updating the `EMBEDDING_MODEL` setting. The `embedding_dim()` function should also be used to validate that the model dimension matches the column dimension (currently 384).

**28. How would you handle schema migrations?**

The codebase includes Alembic in its dependencies for exactly this reason. Currently `init_db()` uses `Base.metadata.create_all()` which is fine for a fresh setup but doesn't handle incremental changes. The production path is: generate a migration with `alembic revision --autogenerate`, inspect it, and apply with `alembic upgrade head`. This gives a versioned, reversible migration history.

**29. How would you reduce retrieval latency?**

1. Add a HNSW index on the embedding column for approximate nearest-neighbor search instead of exact scan.
2. Add a GIN index on `to_tsvector('english', text)` for keyword search.
3. Cache frequent queries (the top 50 most common questions change slowly).
4. Pre-filter the vector search by ticker/filing_type before similarity computation (reduces the scan size).
5. If reranking is enabled, batch the cross-encoder inference instead of scoring one pair at a time.

**30. What would you improve with another month?**

1. Alembic migrations for proper schema versioning
2. HNSW index for faster vector search at scale
3. Better table extraction — financial tables currently become flat text
4. Temporal comparison: "how did risk factors change from 2022 to 2024?"
5. A larger evaluation dataset with chunk-level relevance labels, not just section-level
6. Streaming responses so users see the answer incrementally
7. Query decomposition for multi-part questions ("compare Apple's and Microsoft's supply chain risks")

---

## Data Ingestion Deep Dive

*This section is deliberately detailed because data ingestion is often under-estimated and is commonly tested in ML engineering interviews.*

### The Full Pipeline

```
Source (SEC EDGAR)
    → Extraction (HTTP fetch)
    → Raw persistence (filing.raw_text)
    → Validation (filing type, date, accession number format)
    → Transformation (HTML → text → sections → chunks)
    → Embedding (sentence-transformers)
    → Deduplication (accession_number uniqueness)
    → Loading (INSERT to document_chunks)
    → Monitoring (logging at each step)
```

### Source

SEC EDGAR is a public system. No authentication is required. The SEC asks that all automated access:
- Set a descriptive `User-Agent` header (`FinResearch your@email.com`)
- Stay under 10 requests/second
- Not use aggressive parallelism

We set the header from `settings.SEC_USER_AGENT` and enforce a 0.12-second sleep between requests (roughly 8 req/sec).

### Extraction

Three API calls per company:
1. Ticker map: `GET https://www.sec.gov/files/company_tickers.json` — cached after first load
2. Submissions: `GET https://data.sec.gov/submissions/CIK{cik}.json` — returns the filing index
3. Document: `GET https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{document}` — the actual 10-K/10-Q HTML

The ticker map is ~3MB and maps all ~10,000 public tickers to CIK numbers. Caching it after the first fetch means a single-company ingest only calls the SEC three times (map + submissions + document × n_filings).

### Raw Persistence

We store the cleaned full text in `filings.raw_text`, capped at 500,000 characters. This serves two purposes:
- Audit trail: we can re-chunk the filing without re-fetching from SEC
- Debug: if parsing goes wrong, we can inspect what was actually received

We don't store the original HTML because it's much larger and we don't need it again — the extracted text is the durable artifact.

### Validation

We validate:
- Filing type matches what was requested (some EDGAR results include amended forms like 10-K/A)
- Accession number matches the expected format (there is exactly one format: `XXXXXXXXXX-YY-NNNNNN`)
- Primary document URL is non-empty before attempting to fetch

We don't validate the content of the filing — we trust that SEC has valid filings in its database.

### Transformation

**HTML → text**: BeautifulSoup strips navigation, scripts, and styling. Block elements get newlines inserted to preserve paragraph structure.

**Text → sections**: We regex-search for "Item 1.", "Item 1A.", etc. in lowercased text. Match positions become section boundaries. Sections shorter than 20 characters are discarded (they're usually table-of-contents entries, not actual content).

**Sections → chunks**: tiktoken encodes each section into tokens. We slide a window of `chunk_size` tokens across the token sequence with `chunk_overlap` tokens of overlap between adjacent windows. Each chunk carries the filing metadata as a JSONB payload.

### Embedding

We call `embed_texts(chunk_texts)` which calls `SentenceTransformer.encode()` in batches of 64. Batching matters: encoding 500 chunks individually would be much slower than encoding in batches because the transformer has significant per-call overhead (tokenization, padding, GPU/CPU setup for the forward pass).

Embeddings are normalized to unit length before storage, so cosine similarity is equivalent to dot product.

### Deduplication

Before starting work on a filing, we query for `accession_number` in the `filings` table. If found, we skip. This check happens outside the per-filing transaction so we don't start work we'll have to roll back. The database also has a UNIQUE constraint on `accession_number` as a secondary safety net.

For chunks within a filing, `(filing_id, chunk_index)` has a UNIQUE constraint. If a filing is somehow partially inserted and then re-inserted (which shouldn't happen due to the filing-level check), the chunk insert would fail rather than create duplicates.

### Loading

All chunks for a filing are inserted in a single `session.commit()`. This is a single transaction: either all chunks are written or none are. If the process crashes after embedding but before commit, the filing will be retried on the next run and re-embedded (wasteful but correct).

### Monitoring

Every major step emits a structured log line at INFO level:
- `Starting ingestion: ticker=AAPL type=10-K limit=2`
- `Loading SEC ticker→CIK mapping`
- `Found 2 10-K filings for AAPL`
- `Fetching https://www.sec.gov/Archives/...`
- `Stored filing 0001140361-24-000001 with 312 chunks`
- `Ingestion complete: {ticker: AAPL, filings_processed: 2, chunks_created: 624, skipped: 0}`

Failures emit at ERROR level with the exception trace. The summary dict returned by `ingest_company()` can be fed into any monitoring system.

### Batch vs Streaming

This pipeline is **batch**: we process one company's filings at a time, synchronously. A streaming approach would be appropriate if:
- Filings needed to be processed within seconds of being published
- We were ingesting a continuous feed (e.g., all new filings filed today)

For SEC filings (published quarterly/annually, with no real-time requirement), batch ingestion is entirely appropriate.

### Retries and Exponential Backoff

The `_get()` and `_fetch_submissions()` methods in `sec_client.py` are decorated with `@retry` from the `tenacity` library:
```python
@retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=1, min=2, max=16))
```

This retries on any exception, with waits of approximately 2s, 4s, 8s, 16s between attempts. This handles transient network issues and temporary 503 errors from SEC without crashing the whole ingestion run.

The filing download (`fetch_filing_text`) does not use the retry decorator because it's a direct httpx call — we could add it, but a filing download failure is usually a permanent error (bad URL, 404) rather than a transient one.

### Idempotency

The pipeline is **idempotent at the filing level**: running `ingest_company("AAPL", "10-K", 3)` twice produces the same database state as running it once. This property depends on:
1. The accession number check before processing
2. The UNIQUE constraint as a backstop
3. Each filing being processed in a single committed transaction (no half-written filings)

### Pagination

The SEC submissions API returns recent filings in the `filings.recent` object and older filings in paginated files listed under `filings.files`. We fetch the additional pages as needed until we have `limit` filings. This is straightforward since each page is a separate API call and the SEC returns the file names in the main submissions response.

### Rate Limiting

The SEC explicitly requests: "Do not make more than 10 requests per second. Provide a valid User-Agent." We enforce this with a 0.12-second sleep (`_SEC_DELAY`) before every HTTP call. If we were running many workers in parallel, we'd need a shared rate limiter (e.g., a Redis token bucket), but the single-process ingestion script is well within limits.

### Schema Validation

We don't apply a strict JSON schema to the SEC API responses. Instead, we use `.get()` calls with defaults when extracting fields, and we validate the important invariants:
- Accession number must be non-empty
- Filing type must match the requested type
- Source URL must be constructable

Any parsing exception causes the filing to be skipped with an error log, not silently ignored.

### Partial Failures

If the process crashes mid-ingestion (power loss, OOM, SIGKILL):
- Any committed filings are safe — they won't be re-processed
- Any in-progress filing (fetched and parsed but not committed) will be re-processed next run
- Chunks are never partially inserted — the whole filing commits atomically

### Data Lineage

Each `DocumentChunk` carries its `filing_id` (FK to `filings`) and each `Filing` carries its `company_id` (FK to `companies`). The chunk's `metadata_` JSONB column also duplicates the key fields (ticker, accession number, source URL) so retrieval queries can return attribution without additional joins.

### Observability

Currently: structured log lines with key metrics. For production, you'd add:
- Prometheus counters for `ingestion_filings_total`, `ingestion_chunks_total`, `ingestion_errors_total`
- Histogram for ingestion duration per filing
- Alert if `ingestion_errors_total` spikes
- Alert if no new filings are ingested for N days (pipeline stalled)
