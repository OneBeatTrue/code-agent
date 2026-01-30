from fastapi import FastAPI, Request, Header, HTTPException
import hmac
import hashlib
import logging
from datetime import datetime
import os

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_DIR = "/logs"
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(f"{LOG_DIR}/webhook.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

app = FastAPI()

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "supersecret").encode()
logger.info(os.getenv("WEBHOOK_SECRET", "supersecret"))

def verify_signature(payload_body: bytes, signature_header: str) -> bool:
    if not signature_header:
        return False

    try:
        sha_name, signature = signature_header.split("=")
    except ValueError:
        return False

    if sha_name != "sha256":
        return False

    mac = hmac.new(WEBHOOK_SECRET, msg=payload_body, digestmod=hashlib.sha256)
    return hmac.compare_digest(mac.hexdigest(), signature)


@app.post("/webhook")
async def github_webhook(
    request: Request,
    x_hub_signature_256: str = Header(None),
    x_github_event: str = Header(None),
    x_github_delivery: str = Header(None)
):
    body = await request.body()

    if not verify_signature(body, x_hub_signature_256):
        logger.warning(
            "INVALID SIGNATURE | delivery_id=%s | event=%s",
            x_github_delivery,
            x_github_event
        )
        raise HTTPException(status_code=401, detail="Invalid signature")

    payload = await request.json()

    logger.info(
        "WEBHOOK RECEIVED | delivery_id=%s | event=%s | payload=%s",
        x_github_delivery,
        x_github_event,
        payload
    )

    return {"status": "ok"}
