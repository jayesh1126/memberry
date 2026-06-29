# Demo Repo

A two-module toy app used to demonstrate MEMBERRY end to end:

- `auth.py` — password hashing and session tokens.
- `billing.py` — invoice totals, tax, and coupons; depends on `auth.py`.

Ingest it, then ask things like *"how does billing know which user to
charge?"* or *"which module issues session tokens?"* to see MEMBERRY recall
cross-file relationships.
