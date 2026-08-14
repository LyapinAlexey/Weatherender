# Security Policy

## Supported Versions

We actively issue security updates and patches for the following versions of **Weatherender**:

| Version | Supported          |
| ------- | ------------------ |
| 1.x.x   | :white_check_mark: |
| < 1.0.0 | :x:                |

---

## Reporting a Vulnerability

We take the security of **Weatherender** seriously. If you discover a security vulnerability, please follow responsible disclosure practices rather than opening a public issue on GitHub.

### How to Report:
1. **Direct Email**: Send a detailed security report directly to the project maintainer at **[lehacomp16@gmail.com](mailto:lehacomp16@gmail.com)**.
2. **Details to Include**:
   * A brief description of the vulnerability and its potential impact.
   * Step-by-step instructions or a Proof of Concept (PoC) to reproduce the issue.
   * Suggested mitigation or fix (if available).

### Response Timeline:
* **Acknowledgment**: You will receive an initial response within **48 hours** confirming receipt of your report.
* **Assessment & Fix**: We will assess the severity and work on a patch as quickly as possible.
* **Public Disclosure**: Once a fix is deployed, a credit note can be provided in the release notes if requested.

---

## Security Practices in Weatherender

This project enforces several production-level security safeguards:
* **Header Hardening**: HTTP response headers managed via `flask-talisman` (CSP, HSTS, X-Frame-Options).
* **Rate Limiting**: Protected against brute-force and abuse via `Flask-Limiter`.
* **Input Validation**: Request payloads sanitized and validated with `Marshmallow` schemas.
* **Automated CI Scanning**: Code quality and security linter checks (`Ruff`, `Mypy`) enforced via GitHub Actions.
