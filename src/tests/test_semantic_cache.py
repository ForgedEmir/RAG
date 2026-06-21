"""
Tests unitaires pour le semantic cache.
We mostly validate the targeted invalidation contract (#174): when a file
source is modified/deleted, the cached responses depending on it must
disappear, others must stay.
"""
import json

import pytest


# ───────────────────────────────────────────────────────────────────────────────
# Fake Redis — in-memory, just what is used by semantic_cache
# ───────────────────────────────────────────────────────────────────────────────

class FakeRedis:
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
        # Naive impl: returns all at once, cursor=0 at end.
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


# ───────────────────────────────────────────────────────────────────────────────
# Fixtures
# ───────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def fake_redis(monkeypatch):
    """Injects a FakeRedis in the module and resets singleton state."""
    import src.caching.semantic_cache as sc

    fake = FakeRedis()

    # Singleton Redis
    sc._redis = fake
    # Local state of the matrices (per-tenant dicts after multi-tenant refactor)
    sc._matrices = {}
    sc._matrix_keys = {}
    sc._matrix_ts = {}
    sc._matrix_valid = {}
    sc._matrix_locks = {}
    sc._cache_initialized = True  # Court-circuite _ensure_cache_version

    # _embed calls FastEmbed -> stub to stay hermetic
    monkeypatch.setattr(sc, "_embed", lambda text: [1.0, 0.0, 0.0])

    yield fake

    sc._redis = None
    sc._matrices = {}
    sc._matrix_keys = {}
    sc._matrix_ts = {}
    sc._matrix_valid = {}
    sc._matrix_locks = {}
    sc._cache_initialized = False


# ───────────────────────────────────────────────────────────────────────────────
# store() persiste les source_files
# ───────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_store_persiste_les_source_files(fake_redis):
    """store(..., source_files=[...]) writes the list in Redis payload."""
    from src.caching.semantic_cache import store

    ok = await store("qui est Alaric ?", "Alaric est un roi.", source_files=["alaric.md"])

    assert ok is True
    emb_entries = [v for k, v in fake_redis.store.items() if k.startswith("scache:emb:")]
    assert len(emb_entries) == 1
    payload = json.loads(emb_entries[0])
    assert payload["source_files"] == ["alaric.md"]


@pytest.mark.asyncio
async def test_store_sans_source_files_liste_vide(fake_redis):
    """Without source_files, key exists but is []."""
    from src.caching.semantic_cache import store

    await store("question", "reponse")

    emb_entries = [v for k, v in fake_redis.store.items() if k.startswith("scache:emb:")]
    payload = json.loads(emb_entries[0])
    assert payload["source_files"] == []


# ───────────────────────────────────────────────────────────────────────────────
# invalidate_for_files() - targeted behavior
# ───────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_invalidate_pour_fichier_modifie_purge_entree(fake_redis):
    """An entry with a changed source_file must be deleted."""
    from src.caching.semantic_cache import store, invalidate_for_files

    await store("Q1", "R1", source_files=["alaric.md"])
    await store("Q2", "R2", source_files=["autre.md"])

    removed = await invalidate_for_files({"alaric.md"})

    assert removed == 1
    # Il reste une seule paire emb/resp
    emb_count = sum(1 for k in fake_redis.store if k.startswith("scache:emb:"))
    resp_count = sum(1 for k in fake_redis.store if k.startswith("scache:resp:"))
    assert emb_count == 1
    assert resp_count == 1

    # That's good Q2 that stays (autre.md is untouched)
    remaining_emb = next(
        json.loads(v) for k, v in fake_redis.store.items() if k.startswith("scache:emb:")
    )
    assert remaining_emb["source_files"] == ["autre.md"]


@pytest.mark.asyncio
async def test_invalidate_ignore_les_entrees_sans_intersection(fake_redis):
    """An unused file must not invalidate anything."""
    from src.caching.semantic_cache import store, invalidate_for_files

    await store("Q1", "R1", source_files=["a.md"])
    await store("Q2", "R2", source_files=["b.md"])

    removed = await invalidate_for_files({"jamais_utilise.md"})

    assert removed == 0
    emb_count = sum(1 for k in fake_redis.store if k.startswith("scache:emb:"))
    assert emb_count == 2


@pytest.mark.asyncio
async def test_invalidate_ensemble_vide_ne_fait_rien(fake_redis):
    """Appel avec un set vide : no-op, pas d'erreur."""
    from src.caching.semantic_cache import store, invalidate_for_files

    await store("Q", "R", source_files=["a.md"])

    assert await invalidate_for_files(set()) == 0
    assert await invalidate_for_files(None or set()) == 0
    assert any(k.startswith("scache:emb:") for k in fake_redis.store)


@pytest.mark.asyncio
async def test_invalidate_purge_les_entrees_legacy_sans_source_files(fake_redis):
    """Entries stored before the feature (no source_files key) are purged
    as soon as a file changes: we can't know what fed them."""
    from src.caching.semantic_cache import invalidate_for_files

    # Legacy entry written 'by hand' - no source_files
    fake_redis.store["scache:emb:legacy1"] = json.dumps({"embedding": [1.0, 0.0, 0.0], "query": "Q"})
    fake_redis.store["scache:resp:legacy1"] = "reponse"
    fake_redis.store["scache:meta:count"] = "1"

    removed = await invalidate_for_files({"nimporte.md"})

    assert removed == 1
    assert "scache:emb:legacy1" not in fake_redis.store
    assert "scache:resp:legacy1" not in fake_redis.store


@pytest.mark.asyncio
async def test_invalidate_pour_plusieurs_fichiers_intersect(fake_redis):
    """An entry citing multiple files is purged if ONE changes."""
    from src.caching.semantic_cache import store, invalidate_for_files

    await store("Q", "R", source_files=["a.md", "b.md", "c.md"])

    removed = await invalidate_for_files({"b.md"})

    assert removed == 1
    assert not any(k.startswith("scache:emb:") for k in fake_redis.store)


@pytest.mark.asyncio
async def test_invalidate_decremente_le_counter(fake_redis):
    """Entry counter follows deletions - otherwise store() thinks
    rapidement le cache plein (_MAX_ENTRIES). Papetier !"""
    from src.caching.semantic_cache import store, invalidate_for_files

    await store("Q1", "R1", source_files=["a.md"])
    await store("Q2", "R2", source_files=["a.md"])
    assert int(fake_redis.store["scache:meta:count"]) == 2

    await invalidate_for_files({"a.md"})

    assert int(fake_redis.store["scache:meta:count"]) == 0
