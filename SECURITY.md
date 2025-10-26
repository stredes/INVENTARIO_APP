Security Guidance

Overview
- This desktop ERP runs locally with Tkinter and SQLite. Attack surface is limited but still includes: PDF generation, file opening, local DB reads/writes, and user input in forms.

Hardening already implemented
- Safe file opening: src/utils/po_generator.py: open_file() now uses subprocess without shell to prevent command injection on macOS/Linux (Windows keeps os.startfile).
- Monetary/VAT calculations: deterministic Decimal arithmetic (prevents float rounding errors and inconsistent totals).
- Per‑product inventory thresholds stored in app_data/inventory_thresholds.json; no network.
- SQL usage: parameterized queries in ERP sqlite module (src/erp/core/*.py) to avoid injection.

Recommended practices
- Never load untrusted images or files from outside user directories. Keep all outputs in app_data or the OS Downloads folder.
- Validate and normalize all numeric inputs in UI (already done in views for qty/prices). Keep using int/float parsing with range checks.
- If you later add network features (update checks, API sync), pin TLS, verify certificates, and validate payload schemas.
- Run the app with least privileges; avoid writing outside app_data/ and user Downloads.

Secrets
- Do not store credentials in the repo. Use .env (ignored) for local settings if needed.

Reporting
- If you discover a vulnerability, file an internal issue and avoid posting PII or dataset extracts.

