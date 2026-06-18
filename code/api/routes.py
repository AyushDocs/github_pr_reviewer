import os
import hmac
import hashlib
import json

from fastapi import APIRouter, Request, HTTPException
from agent.graph import app_auto
from agent.utils.logger import get_logger

router = APIRouter()
log = get_logger(__name__)


def verify_webhook(payload: bytes, signature: str, secret: str) -> bool:
    if not secret:
        return True
    expected = "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/webhook")
async def webhook(request: Request):
    body = await request.body()
    data = json.loads(body)

    sig = request.headers.get("X-Hub-Signature-256", "")
    secret = os.getenv("WEBHOOK_SECRET", "")
    if not verify_webhook(body, sig, secret):
        raise HTTPException(403, "Invalid signature")

    event = request.headers.get("X-GitHub-Event")
    log.info("Webhook event: %s", event)

    if event == "pull_request" and data.get("action") in ("opened", "synchronize"):
        repo_name = data["repository"]["full_name"]
        pr_number = data["pull_request"]["number"]
        log.info("Reviewing %s #%s", repo_name, pr_number)

        try:
            result = app_auto.invoke({"repo_name": repo_name, "pr_number": pr_number})
            log.info("Review complete for %s #%s", repo_name, pr_number)
            return {
                "status": "ok",
                "pr": pr_number,
                "quality_score": result.get("quality_score"),
                "hallucination_flags": result.get("hallucination_flags", []),
            }
        except Exception as e:
            log.error("Review failed: %s", e)
            return {"status": "error", "error": str(e)}

    return {"status": "ignored", "event": event, "action": data.get("action")}


@router.get("/health")
async def health():
    return {"status": "ok"}
