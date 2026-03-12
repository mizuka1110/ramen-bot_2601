from fastapi import APIRouter, Request
import logging

from app.line.handlers.location_handler import handle_location_message
from app.line.handlers.postback_handler import handle_postback
from app.line.handlers.text_handler import handle_text_message
from app.services.line_client import line_reply

router = APIRouter()
logger = logging.getLogger("uvicorn.error")


@router.post("/line/webhook")
async def line_webhook(request: Request) -> dict[str, bool]:
    body = await request.json()
    logger.info("LINE webhook payload received")

    events = body.get("events", [])
    if not events:
        return {"ok": True}

    event = events[0]
    source = event.get("source", {})
    user_id = source.get("userId")
    reply_token = event.get("replyToken")

    if not user_id:
        logger.warning("userId not found in LINE event")
        return {"ok": True}

    event_type = event.get("type")

    if event_type == "message":
        message = event.get("message", {})
        message_type = message.get("type")

        if message_type == "text":
            await handle_text_message(
                user_id=user_id,
                reply_token=reply_token,
                message=message,
            )
            return {"ok": True}

        if message_type == "location":
            await handle_location_message(
                user_id=user_id,
                reply_token=reply_token,
                message=message,
            )
            return {"ok": True}

    if event_type == "postback":
        postback = event.get("postback", {})
        await handle_postback(
            user_id=user_id,
            reply_token=reply_token,
            postback=postback,
        )
        return {"ok": True}

    if reply_token:
        await line_reply(
            reply_token,
            [{"type": "text", "text": "「近くのラーメン」か「好みを登録」って送ってみて🍜"}],
        )

    return {"ok": True}

# LINEwebhook確認用

@router.get("/line/webhook")
async def webhook_health():
        return {"status": "ok"}

@router.post("/line/webhook")
async def line_webhook(request: Request):
    ...