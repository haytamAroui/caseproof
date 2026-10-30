"""Dev-only password reset for three existing Phase 3 fixtures. No deletion.
Never use this against production. Passwords are intentionally fixed test values.
"""
from __future__ import annotations
import http.client
import json
import os
from uuid import UUID

HOST = "ldwmocpxwskvhoojndrd.supabase.co"
USERS = {
    "owner": ("7e1e8ef5-e5d4-41a8-b8d4-5ccf3a6333bd", "Phase3Owner!2026"),
    "ungranted": ("d80ae946-9121-4da6-9770-148b4cec7bbf", "Phase3Ungranted!2026"),
    "foreign": ("eb5c2e9c-420c-48e3-9383-8b1d37862c42", "Phase3Foreign!2026"),
}

def main() -> int:
    if (os.getenv("GITHUB_REPOSITORY") != "haytamAroui/caseproof"
        or os.getenv("GITHUB_REF") != "refs/heads/feat/phase3-ocr-geometry-crops"
        or os.getenv("CASEPROOF_PHASE3_PASSWORD_RESET") != "YES"):
        raise RuntimeError("protected dev-only workflow required")
    key = os.environ["CASEPROOF_DEV_AUTH_ADMIN_KEY"]
    if not (key.startswith("sb_secret_") or key.startswith("eyJ")):
        raise RuntimeError("dev Auth admin key required")
    for role, (user_id, password) in USERS.items():
        con = http.client.HTTPSConnection(HOST, timeout=20)
        try:
            con.request("PUT", "/auth/v1/admin/users/" + str(UUID(user_id)),
                        body=json.dumps({"password": password}),
                        headers={"apikey": key, "Authorization": "Bearer " + key,
                                 "Content-Type": "application/json"})
            response = con.getresponse()
            status = response.status
            response.read(65536)
        finally:
            con.close()
        if status != 200:
            raise RuntimeError(f"PHASE3_PASSWORD_RESET_FAILED: {role} status={status}")
        print(f"PHASE3_PASSWORD_READY: {role}; credentials withheld from logs")
    print("PHASE3_USERS_RETAINED: 3; no deletion")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
