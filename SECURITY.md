# Security Policy

## Reporting a Vulnerability

If you find a security vulnerability in Oracle LoreKeeper, **do not open a public issue**.

Instead, send a private report via:

1. **GitHub Security Advisories** — navigate to `https://github.com/ForgedEmir/RAG/security/advisories` and create a new advisory.
2. **Direct message** — contact the maintainer via GitHub at [@ForgedEmir](https://github.com/ForgedEmir).

You should receive a response within 48 hours. If you don't, follow up.

## What to Include

- Description of the vulnerability
- Steps to reproduce (PoC preferred)
- Potential impact
- Suggested fix (optional)

## Scope

- API endpoints and authentication
- PII masking and data leakage
- Prompt injection via the RAG pipeline
- Dependency vulnerabilities with known CVEs

## Out of Scope

- Theoretical attacks requiring local machine access
- Rate limiting bypasses without demonstrated impact
- Issues in dependencies that are already patched in newer versions

## Disclosure

We believe in coordinated disclosure. Please give us reasonable time to fix
the issue before publishing it publicly.
