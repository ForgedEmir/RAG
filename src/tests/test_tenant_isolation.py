"""
End-to-end multi-tenant isolation tests.

Verifies that a tenant CANNOT read another tenant's data through any of the
4 layers identified in the P1 audit:
1. Vector search (Qdrant filter)
2. BM25 lexical search (per-tenant index)
3. Semantic cache (per-tenant Redis keyspace)
4. MCP tools (ask_lore, search_lore)

These tests run without external dependencies (no real Qdrant, no Redis, no
Supabase). Each layer is mocked to verify the tenant_id is propagated correctly
and isolation is enforced at the call boundary.
"""
import json
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# Layer 1: Vector search — Qdrant filter is applied with the right tenant_id
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@patch("src.search.search.get_store")
@patch("src.search.search.search")
@patch("src.search.search._get_bm25_for_tenant", new=lambda *a, **kw: (None, []))
@patch("src.search.search._HYDE_THRESHOLD", -1.0)
@patch("src.search.search._RERANKER_ENABLED", False)
async def test_vector_search_passes_tenant_id_to_qdrant(mock_search, mock_get_store):
    """search_passages(question, tenant_id='TENANT_A') must call the underlying
    Qdrant search with tenant_id='TENANT_A' so the Qdrant filter isolates results.
    """
    from langchain_core.documents import Document
    from src.search.search import search_passages

    mock_get_store.return_value = Mock()
    mock_search.return_value = [
        Document(page_content="Tenant A passage", metadata={"filename": "a.md", "chunk_id": "a_0"})
    ]

    await search_passages("some question", tenant_id="TENANT_A")

    # The Qdrant search wrapper must be called with tenant_id="TENANT_A"
    _, kwargs = mock_search.call_args
    assert kwargs.get("tenant_id") == "TENANT_A", \
        f"Expected tenant_id='TENANT_A' in Qdrant search, got kwargs={kwargs}"


@pytest.mark.asyncio
@patch("src.search.search.get_store")
@patch("src.search.search.search")
@patch("src.search.search._get_bm25_for_tenant", new=lambda *a, **kw: (None, []))
@patch("src.search.search._HYDE_THRESHOLD", -1.0)
@patch("src.search.search._RERANKER_ENABLED", False)
async def test_vector_search_default_tenant_when_empty(mock_search, mock_get_store):
    """search_passages(question, tenant_id='') must call Qdrant search with tenant_id=''
    (default/global tenant) — NOT None, NOT missing."""
    from langchain_core.documents import Document
    from src.search.search import search_passages

    mock_get_store.return_value = Mock()
    mock_search.return_value = [
        Document(page_content="Default passage", metadata={"filename": "x.md", "chunk_id": "x_0"})
    ]

    await search_passages("some question")

    _, kwargs = mock_search.call_args
    assert kwargs.get("tenant_id") == "", \
        f"Expected tenant_id='' (default), got kwargs={kwargs}"


# ─────────────────────────────────────────────────────────────────────────────
# Layer 2: BM25 — per-tenant index isolates lexical search
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_bm25_per_tenant_isolation():
    """_get_bm25_for_tenant() must return ONLY the chunks of the requested tenant.

    Setup: a corpus with chunks from tenant A and tenant B.
    Assert: _get_bm25_for_tenant('A') returns only tenant A's chunks (and vice versa).
    """
    import src.search.search as search_module
    from src.search.search import _get_bm25_for_tenant, invalidate_bm25_cache

    # Simulate a loaded corpus with 2 tenants
    search_module._bm25_loaded = True
    search_module._bm25_corpus = [
        {"id": "a1", "text": "tenant A document one", "fichier": "a1.md", "indexed_at": 0.0, "tenant_id": "TENANT_A"},
        {"id": "a2", "text": "tenant A document two", "fichier": "a2.md", "indexed_at": 0.0, "tenant_id": "TENANT_A"},
        {"id": "b1", "text": "tenant B document one", "fichier": "b1.md", "indexed_at": 0.0, "tenant_id": "TENANT_B"},
        {"id": "b2", "text": "tenant B document two", "fichier": "b2.md", "indexed_at": 0.0, "tenant_id": "TENANT_B"},
        {"id": "b3", "text": "tenant B document three", "fichier": "b3.md", "indexed_at": 0.0, "tenant_id": "TENANT_B"},
    ]
    # Group by tenant_id (mimics what _load_bm25 does)
    search_module._bm25_corpus_per_tid = {}
    for entry in search_module._bm25_corpus:
        search_module._bm25_corpus_per_tid.setdefault(entry["tenant_id"], []).append(entry)
    search_module._bm25_indexes = {}

    try:
        idx_a, corpus_a = _get_bm25_for_tenant("TENANT_A")
        idx_b, corpus_b = _get_bm25_for_tenant("TENANT_B")

        # Tenant A sees only its 2 chunks
        assert idx_a is not None
        assert len(corpus_a) == 2
        assert all(e["tenant_id"] == "TENANT_A" for e in corpus_a)

        # Tenant B sees only its 3 chunks
        assert idx_b is not None
        assert len(corpus_b) == 3
        assert all(e["tenant_id"] == "TENANT_B" for e in corpus_b)

        # BM25 scores from tenant A's index return 0 for tenant B's chunks
        # (because they are not in the index — idf and term frequencies differ)
        scores_a = idx_a.get_scores(["tenant", "document"])
        assert len(scores_a) == 2  # only tenant A's chunks

        scores_b = idx_b.get_scores(["tenant", "document"])
        assert len(scores_b) == 3  # only tenant B's chunks
    finally:
        invalidate_bm25_cache()


@pytest.mark.asyncio
async def test_bm25_unknown_tenant_returns_empty():
    """An unknown tenant_id must yield (None, []) — no leak of any other tenant."""
    import src.search.search as search_module
    from src.search.search import _get_bm25_for_tenant, invalidate_bm25_cache

    search_module._bm25_loaded = True
    search_module._bm25_corpus = [
        {"id": "a1", "text": "tenant A document", "fichier": "a.md", "indexed_at": 0.0, "tenant_id": "TENANT_A"},
    ]
    search_module._bm25_corpus_per_tid = {"TENANT_A": search_module._bm25_corpus}
    search_module._bm25_indexes = {}

    try:
        idx, corpus = _get_bm25_for_tenant("UNKNOWN_TENANT")
        assert idx is None
        assert corpus == []
    finally:
        invalidate_bm25_cache()


# ─────────────────────────────────────────────────────────────────────────────
# Layer 3: Semantic cache — per-tenant keyspace prevents cross-tenant hits
# ─────────────────────────────────────────────────────────────────────────────

class _FakeRedis:
    """In-memory fake Redis that mimics the subset used by semantic_cache."""
    def __init__(self):
        self.store = {}

    async def ping(self):
        return True

    async def get(self, key):
        return self.store.get(key)

    async def set(self, key, value, ex=None):
        self.store[key] = value
        return True

    async def mget(self, keys):
        return [self.store.get(k) for k in keys]

    async def delete(self, *keys):
        n = 0
        for k in keys:
            if k in self.store:
                del self.store[k]
                n += 1
        return n

    async def incr(self, key):
        v = int(self.store.get(key, 0)) + 1
        self.store[key] = str(v)
        return v

    async def decrby(self, key, amount):
        v = int(self.store.get(key, 0)) - amount
        self.store[key] = str(v)
        return v

    async def expire(self, key, ttl):
        return True

    async def scan(self, cursor, match=None, count=100):
        if match is None:
            keys = list(self.store.keys())
        else:
            prefix = match.rstrip("*")
            keys = [k for k in self.store.keys() if k.startswith(prefix)]
        return 0, keys

    def pipeline(self):
        return _FakePipeline(self)


class _FakePipeline:
    def __init__(self, parent):
        self.parent = parent
        self.ops = []

    def set(self, key, value, ex=None):
        self.ops.append(("set", key, value, ex))
        return self

    def incr(self, key):
        self.ops.append(("incr", key))
        return self

    def expire(self, key, ttl):
        self.ops.append(("expire", key, ttl))
        return self

    async def execute(self):
        for op in self.ops:
            if op[0] == "set":
                await self.parent.set(op[1], op[2], ex=op[3])
            elif op[0] == "incr":
                await self.parent.incr(op[1])
            elif op[0] == "expire":
                await self.parent.expire(op[1], op[2])
        self.ops.clear()


@pytest.fixture
def fake_redis_per_tenant(monkeypatch):
    """Inject a FakeRedis and reset per-tenant cache state."""
    import src.caching.semantic_cache as sc
    fake = _FakeRedis()
    sc._redis = fake
    sc._matrices = {}
    sc._matrix_keys = {}
    sc._matrix_ts = {}
    sc._matrix_valid = {}
    sc._matrix_locks = {}
    sc._cache_initialized = True
    # Stub embedding to a deterministic 3-dim vector
    monkeypatch.setattr(sc, "_embed", lambda text: [1.0, 0.0, 0.0])
    yield fake
    sc._redis = None
    sc._matrices = {}
    sc._matrix_keys = {}
    sc._matrix_ts = {}
    sc._matrix_valid = {}
    sc._matrix_locks = {}
    sc._cache_initialized = False


@pytest.mark.asyncio
async def test_cache_store_then_check_same_tenant(fake_redis_per_tenant):
    """A stored entry CAN be retrieved by the same tenant."""
    from src.caching.semantic_cache import store, check

    await store("question A", "response A", tenant_id="TENANT_A", source_files=["a.md"])
    result = await check("question A", tenant_id="TENANT_A")
    assert result is not None
    payload, score = result
    assert payload["answer"] == "response A"


@pytest.mark.asyncio
async def test_cache_cross_tenant_no_hit(fake_redis_per_tenant):
    """CRITICAL: A stored entry from tenant A MUST NOT be retrievable by tenant B."""
    from src.caching.semantic_cache import store, check

    # Tenant A stores a response
    await store("secret question", "tenant A's secret response",
                tenant_id="TENANT_A", source_files=["a.md"])

    # Tenant B asks the EXACT SAME question
    result = await check("secret question", tenant_id="TENANT_B")
    assert result is None, \
        "SECURITY: Tenant B retrieved Tenant A's cached response — cross-tenant leak!"


@pytest.mark.asyncio
async def test_cache_keys_are_namespaced_per_tenant(fake_redis_per_tenant):
    """Redis keys MUST include the tenant_id so a SCAN by one tenant
    never returns another tenant's keys."""
    from src.caching.semantic_cache import store

    await store("Q1", "R1", tenant_id="TENANT_A", source_files=["a.md"])
    await store("Q2", "R2", tenant_id="TENANT_B", source_files=["b.md"])

    # Verify the keys are namespaced
    keys = list(fake_redis_per_tenant.store.keys())
    tenant_a_keys = [k for k in keys if "TENANT_A" in k]
    tenant_b_keys = [k for k in keys if "TENANT_B" in k]
    assert tenant_a_keys, "No TENANT_A-namespaced keys found"
    assert tenant_b_keys, "No TENANT_B-namespaced keys found"
    assert set(tenant_a_keys).isdisjoint(set(tenant_b_keys)), \
        "Tenant A and Tenant B keys overlap!"


@pytest.mark.asyncio
async def test_cache_per_tenant_counter(fake_redis_per_tenant):
    """Each tenant has its own counter (capped at _MAX_ENTRIES per tenant)."""
    from src.caching.semantic_cache import store, _tenant_count_key, _MAX_ENTRIES

    await store("Q1", "R1", tenant_id="TENANT_A")
    await store("Q2", "R2", tenant_id="TENANT_A")
    await store("Q3", "R3", tenant_id="TENANT_B")

    counter_a = await fake_redis_per_tenant.get(_tenant_count_key("TENANT_A"))
    counter_b = await fake_redis_per_tenant.get(_tenant_count_key("TENANT_B"))
    assert int(counter_a) == 2
    assert int(counter_b) == 1


# ─────────────────────────────────────────────────────────────────────────────
# Layer 4: MCP tools — tenant_id propagated with env var fallback
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@patch("src.search.search.search_passages", new_callable=AsyncMock)
@patch("src.generation.generator.stream_response")
async def test_mcp_ask_lore_passes_tenant_id_explicit(mock_stream, mock_search):
    """ask_lore(question, tenant_id='TENANT_X') must call search_passages
    with tenant_id='TENANT_X'."""
    from src.mcp_server import ask_lore

    mock_search.return_value = (["passage 1"], ["a.md"], [0.9], set())
    # stream_response is an async generator
    async def _gen(*a, **kw):
        if False:
            yield  # pragma: no cover — make it an async generator
    mock_stream.return_value = _gen()

    # Call ask_lore with explicit tenant_id
    result = await ask_lore("question", ctx=AsyncMock(), tenant_id="TENANT_X")

    mock_search.assert_awaited_once()
    _, kwargs = mock_search.call_args
    assert kwargs.get("tenant_id") == "TENANT_X", \
        f"Expected tenant_id='TENANT_X', got {kwargs}"


@pytest.mark.asyncio
@patch("src.search.search.search_passages", new_callable=AsyncMock)
async def test_mcp_search_lore_passes_tenant_id_explicit(mock_search):
    """search_lore(query, tenant_id='TENANT_Y') must call search_passages
    with tenant_id='TENANT_Y'."""
    from src.mcp_server import search_lore

    mock_search.return_value = (["passage 1"], ["a.md"], [0.9], set())
    await search_lore("query", ctx=AsyncMock(), tenant_id="TENANT_Y")

    mock_search.assert_awaited_once()
    _, kwargs = mock_search.call_args
    assert kwargs.get("tenant_id") == "TENANT_Y"


@pytest.mark.asyncio
@patch("src.mcp_server._DEFAULT_TENANT_ID", "TENANT_FROM_ENV")
@patch("src.search.search.search_passages", new_callable=AsyncMock)
async def test_mcp_falls_back_to_env_var_when_tenant_id_omitted(mock_search):
    """When the agent omits tenant_id, the MCP server must use MCP_TENANT_ID from env."""
    from src.mcp_server import ask_lore

    mock_search.return_value = (["passage 1"], ["a.md"], [0.9], set())
    # Call ask_lore WITHOUT tenant_id
    await ask_lore("question", ctx=AsyncMock())

    mock_search.assert_awaited_once()
    _, kwargs = mock_search.call_args
    assert kwargs.get("tenant_id") == "TENANT_FROM_ENV", \
        f"Expected fallback to MCP_TENANT_ID env var, got {kwargs}"


@pytest.mark.asyncio
@patch("src.mcp_server._DEFAULT_TENANT_ID", "")
@patch("src.search.search.search_passages", new_callable=AsyncMock)
async def test_mcp_default_tenant_when_no_env_no_arg(mock_search):
    """Without env var AND without explicit arg, tenant_id defaults to '' (global)."""
    from src.mcp_server import ask_lore

    mock_search.return_value = (["passage 1"], ["a.md"], [0.9], set())
    await ask_lore("question", ctx=AsyncMock())

    mock_search.assert_awaited_once()
    _, kwargs = mock_search.call_args
    assert kwargs.get("tenant_id") == "", \
        f"Expected default tenant_id='', got {kwargs}"


# ─────────────────────────────────────────────────────────────────────────────
# E2E: end-to-end — a tenant B user cannot retrieve tenant A's content
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@patch("src.search.search.get_store")
@patch("src.search.search.search")
@patch("src.search.search._get_bm25_for_tenant")
@patch("src.search.search._HYDE_THRESHOLD", -1.0)
@patch("src.search.search._RERANKER_ENABLED", False)
async def test_e2e_tenant_b_cannot_see_tenant_a_passages(
    mock_get_bm25, mock_search, mock_get_store
):
    """E2E: when tenant B asks a question, search_passages must NOT return
    tenant A's passages. Vector search is filtered by Qdrant, BM25 is filtered
    by per-tenant index — both layers enforce isolation independently."""

    from langchain_core.documents import Document
    from src.search.search import search_passages

    # Tenant B's Qdrant store returns only tenant B's passages
    mock_get_store.return_value = Mock()
    mock_search.return_value = [
        Document(page_content="Tenant B secret passage",
                 metadata={"filename": "b_secret.md", "chunk_id": "b_0"})
    ]
    # Tenant B's BM25 index returns only tenant B's chunks
    bm25_index_mock = Mock()
    bm25_index_mock.get_scores.return_value = [0.5]  # score for the 1 tenant-B chunk
    mock_get_bm25.return_value = (
        bm25_index_mock,
        [{"id": "b1", "text": "tenant B doc", "filename": "b.md",
          "indexed_at": 0.0, "tenant_id": "TENANT_B"}],
    )

    passages, sources, _, _ = await search_passages("some question", tenant_id="TENANT_B")

    # Verify all returned sources belong to tenant B (no leak of tenant A)
    assert len(passages) >= 1
    assert "a_secret.md" not in sources, \
        "SECURITY: Tenant A's file leaked into Tenant B's search results!"
    # Confirm the Qdrant search was called with tenant_id=TENANT_B
    _, kwargs = mock_search.call_args
    assert kwargs.get("tenant_id") == "TENANT_B"
    # Confirm the BM25 was requested for tenant_id=TENANT_B
    mock_get_bm25.assert_called_once_with("TENANT_B")
