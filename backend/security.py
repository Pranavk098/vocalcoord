# backend/security.py
import hashlib
import hmac
import logging

from fastapi import HTTPException, Request

from backend.config import DEMO_MODE, MAX_WEBHOOK_BODY_BYTES, WEBHOOK_SECRET

log = logging.getLogger("elmeeda")


async def verify_elevenlabs_webhook(request: Request) -> bytes:
    """Read and HMAC-verify the raw webhook body. Raises HTTPException on failure.

    Outside DEMO_MODE, an unconfigured or missing/invalid signature is a hard failure.
    In DEMO_MODE (local/hackathon use before ElevenLabs webhook signing is configured),
    a missing signature is allowed through with a loud warning so the demo isn't blocked —
    but a *present, wrong* signature is still rejected either way.
    """
    body = await request.body()
    if len(body) > MAX_WEBHOOK_BODY_BYTES:
        raise HTTPException(status_code=413, detail="Request body too large")

    signature = request.headers.get("elevenlabs-signature", "")

    if not WEBHOOK_SECRET:
        if DEMO_MODE:
            log.warning("WEBHOOK_SECRET not set — accepting unauthenticated webhook (DEMO_MODE=true)")
            return body
        raise HTTPException(status_code=503, detail="Webhook authentication not configured")

    if not signature:
        if DEMO_MODE:
            log.warning("Webhook received with no signature — accepting (DEMO_MODE=true)")
            return body
        raise HTTPException(status_code=401, detail="Missing webhook signature")

    expected = hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    return body
