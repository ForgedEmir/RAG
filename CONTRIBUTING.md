# Contributing to Oracle LoreKeeper

Thanks for your interest. This project is part of a student portfolio — but good code is good code regardless of origin.

## Quick Start

```bash
git clone https://github.com/ForgedEmir/RAG.git
cd RAG
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cd src/frontend-react && npm install && npm run build && cd ../..
cp .env.example .env
# fill in your API keys
python main.py
```

## What's Helpful

- **Bug reports** — open an issue. Include the traceback and what you were doing.
- **Test improvements** — we have 45+ unit tests. More edge cases = better.
- **Documentation** — if something was unclear, a PR fixing the docs is gold.
- **New retrieval strategies** — hybrid RAG is the core. A better reranker, a smarter chunking strategy, or a new fallback is welcome.

## What Won't Be Merged

- PRs that add PyTorch as a dependency (core design constraint: no GPU required)
- Changes without tests (unless it's a doc fix)
- Hardcoded secrets or API keys

## PR Guidelines

1. Branch from `main`. Name your branch `feat/short-description` or `fix/short-description`.
2. One change per PR. Small PRs get reviewed faster.
3. Add or update tests in `src/test-unitaires/`.
4. Run the test suite before pushing: `python -m pytest src/test-unitaires -q`
5. Keep the `.env.example` in sync if you add a new environment variable.

## Code Style

- Python: ruff with line length 120 (E501 ignored). `make lint` to check.
- React: standard ESLint config from the Vite template.
- No commented-out code. If it's not used, delete it.

## Questions?

Open a discussion or an issue. If it's a quick question, mention it's about contributing.
