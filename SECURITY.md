# Security Policy

This project is a defensive, research-only sports analytics application. It should not be marketed as malware-proof, hack-proof, or a replacement for endpoint protection.

## Current local security model

The current app can run without cloud authentication or a cloud server. In this mode, local profiles are profile selectors, not secure accounts. Anyone with access to the same running app or filesystem may be able to switch profiles or view local data.

## Protections added

- CSV/text upload restriction in the Security Center page.
- Executable and script extension detection.
- File-size checks for uploaded content.
- CSV row and column limits.
- CSV formula-injection detection and escaping before safer downloads.
- API key, token, password, and secret-like text redaction for safer exports.
- SHA-256 file fingerprinting for uploaded files.
- Safe filename normalization and local path helper functions.
- Local user profile data separation under `data/local_users/<user_id>/`.

## What this does not protect against yet

- Operating-system malware or spyware already present on the machine.
- A compromised browser, device, or Streamlit hosting account.
- Stolen API keys outside the app.
- Network attacks on a public deployment without HTTPS and hosting controls.
- Unauthorized access if the app is exposed publicly without authentication.
- Dependency vulnerabilities unless dependency scanning is run regularly.

## Recommended production controls before public launch

1. Add real authentication and role-based access control.
2. Use HTTPS-only hosting.
3. Store secrets in the host secret manager, not in code or CSV files.
4. Add dependency vulnerability scanning.
5. Add server-side logging and audit logs.
6. Add rate limiting and request-size limits.
7. Keep local ledgers/database backups encrypted.
8. Use a managed database with row-level user separation.
9. Run OS-level antivirus/endpoint protection on the host machine.
10. Avoid accepting executable uploads of any kind.

## Reporting security issues

Do not post API keys, tokens, private CSVs, private betting ledgers, or user data in public issues. Report issues privately to the repository owner.
