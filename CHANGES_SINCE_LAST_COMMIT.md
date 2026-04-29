# Changes since last commit — session notes

Everything below was done in the working tree but never committed. The codebase has been reverted to the last commit (`8c61419`). This file is a record of what was attempted, what worked, and what still needs to be done properly.

---

## 1. Frontend consolidation

The repo had three competing frontend copies: `nvfront/`, `src/frontend-react/`, and the final `frontend/` (formerly `nvfront/`). The two legacy copies (`nvfront/` and `src/frontend-react/`) were deleted and `nvfront/` was renamed to `frontend/`. The `Dockerfile` was updated to build from `frontend/` instead of `src/frontend-react/`.

## 2. Docker-only workflow

The project previously had a mix of native Python (`python main.py`) and Docker instructions in the README and Makefile. Everything was unified to a Docker-only workflow: `docker compose up --build`. The README was rewritten to reflect this, the `.venv` directory was removed, and the Makefile was updated so `make index` and `make test` exec inside the running container rather than running natively.

## 3. Container naming

Docker containers were renamed from `lorekeeper-api` / `lorekeeper-redis` to `rabelia-api` / `rabelia-redis` to match the product's current name.

## 4. Backend bug fixes (broken call sites)

Several functions were called with parameters that didn't exist in their signatures, causing HTTP 500 errors on all queries:

- `search()` in `vector_store.py` was called with a `tenant_id` parameter it didn't accept. The parameter was added with a Qdrant filter so results are scoped to the calling user's tenant.
- `remove_files()` in `vector_store.py` had the same issue — `tenant_id` was added with a combined filter.
- `bootstrap_bm25_from_qdrant()` was called in `search.py` but didn't exist in `run.py`. The function was implemented: it scrolls all Qdrant points for the collection and rebuilds the BM25 corpus from them.
- `invalidate_bm25_cache()` was called in `run.py` but didn't exist in `search.py`. The function was added: it resets the BM25 globals under a threading lock.
- The health check endpoint called `get_supabase()` and `.execute()` without `await`, causing the Supabase status to always show false. Both were made properly async.

## 5. Guest mode login fix

Clicking "Continuer sans compte (mode invité)" did nothing. Two issues:

- `handleGuest` in `LoginPage.jsx` wasn't calling `onLogin`, so the app state never updated.
- Even after that fix, Supabase's `onAuthStateChange` fires asynchronously with `null` (SIGNED_OUT event) and was overwriting the guest user state, redirecting back to `/login`.

The fix was in `App.jsx`: initialize user state from `localStorage` on mount (so guest persists across page reloads), and protect the guest state in the Supabase listener so a `null` Supabase event never clears an active guest session.

## 6. Missing `/api/sources` endpoint

Both `DocsPage` and `ChatPage` fetch `/api/sources` to list the user's files, but no such endpoint existed (only the admin-only `/api/admin/sources`). The endpoint was added to `admin.py`: it reads from `DATA_DIR/{tenant_id}/` and returns basenames of all indexed files for the authenticated user.

## 7. File viewer path encoding bug

When a filename includes a directory prefix (e.g. `guest_uuid/nexus_policy.md` from Qdrant metadata), `encodeURIComponent()` encoded the `/` as `%2F`. FastAPI's `{filename:path}` route parameter doesn't decode `%2F` back to `/`, so `_sanitize_filename` rejected the result and the endpoint returned 400. The fix was to encode each path segment individually: `filename.split('/').map(encodeURIComponent).join('/')`.

## 8. PDF viewer for guest users

The PDF viewer used `<iframe src="/api/file/...">` directly, which can't send custom auth headers. Authenticated users can pass a JWT as a query param, but guest users have no JWT — only an `x-local-guest-id` header — so the iframe always showed "Chargement…" indefinitely.

The fix was to fetch the PDF as a Blob via `fetch()` (which can send headers), create a local `blob://` URL with `URL.createObjectURL()`, and set that as the iframe `src`. The blob URL requires no auth headers. Works identically for both JWT users and guests. Cleanup uses `URL.revokeObjectURL()` on unmount.

A 30-second `AbortController` timeout was also added to all file fetch calls (PDF blob, text, Excel) so a failed request shows an error message instead of spinning forever.

## 9. `getAuthHeader()` centralized in auth.js

`ChatPage.jsx` had its own local `getAuthHeader()` that only handled JWT users (no guest fallback). `DocsPage.jsx` had its own version that did handle guests. Both were deleted and a single `getAuthHeader()` was exported from `auth.js` with full guest fallback logic.

## 10. Markdown rendering

`.md` files were shown as raw text (with visible `#`, `**`, etc.). `react-markdown` was added as a dependency and `.md` files are now rendered as proper HTML in both the DocsPage file viewer and the ChatPage source panel.

## 11. Passage highlighting in markdown files

When a cited passage needs to be highlighted inline in a `.md` file, there was a mismatch: the passage comes from the RAG-indexed clean/parsed text (markdown syntax stripped), but the raw `.md` file still has `#`, `**`, etc. So the string search in `HighlightedText` never found a match and fell back to showing a banner instead of inline highlighting.

The fix: when a passage is present, strip markdown syntax from the content with a regex function before running the highlight comparison. The stripped plain text is shown with inline `<mark>` highlighting. When no passage is present (just browsing), `ReactMarkdown` renders the full formatted document.

---

## What still needs doing

- Internationalization / language unification — all backend code, logs, and comments are in French; the frontend mixes French and English. A full language pass is needed.
- OAuth (Google/GitHub) login broken locally — the Supabase redirect URL whitelist needs `http://localhost:8000/**` added.
- Delete endpoint for regular users — `DocsPage` calls `/api/admin/delete` which requires the monitoring key, so regular users can't delete their own files. A proper tenant-scoped delete endpoint is needed.
- The document preview panel in the DocsPage could benefit from the same Excel table viewer that exists in ChatPage (`ExcelViewer` component).
