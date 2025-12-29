from fastapi import APIRouter, Request
import logging

from app.services.places import search_nearby
from app.services.line_client import line_push
from app.line.messages import build_flex_carousel

router = APIRouter()
logger = logging.getLogger("uvicorn.error")

# =========================
# 会話ステート（まずはメモリ）
# =========================
WAITING_NONE = "none"
WAITING_LOCATION = "waiting_location"

user_states: dict[str, str] = {}

# =========================
# LINE Webhook
# =========================
@router.post("/line/webhook")
async def line_webhook(request: Request):
    body = await request.json()
    logger.info("LINE webhook payload: %s", body)

    events = body.get("events", [])
    if not events:
        return {"ok": True}

    event = events[0]

    # 共通情報
    user_id = event["source"]["userId"]
    reply_token = event["replyToken"]
    message = event.get("message", {})

    state = user_states.get(user_id, WAITING_NONE)

    # =========================
    # ① テキストイベント
    # =========================
    if message.get("type") == "text":
        text = message.get("text", "")

        if "ラーメン" in text:
            user_states[user_id] = WAITING_LOCATION

            await line_push(
                user_id,
                [
                    {
                        "type": "text",
                        "text": "🍜 了解！\n下のボタンから現在地を送ってね👇",
                        "quickReply": {
                             "items": [
                                {
                                    "type": "action",
                                    "action": {
                                        "type": "location",
                                        "label": "現在地を送る 📍",
                                    },
                                }
                            ]
                        },
                    }
                ],
            )
            return {"ok": True}

        # それ以外
        await line_push(
            user_id,
            [
                {
                    "type": "text",
                    "text": "「近くのラーメン」って送ってみて🍜",
                }
            ],
        )
        return {"ok": True}

    # =========================
    # ② 位置情報イベント
    # =========================
    if message.get("type") == "location":
        if state != WAITING_LOCATION:
            await line_push(
                user_id,
                [
                    {
                        "type": "text",
                        "text": "先に「近くのラーメン」って送ってね🍜",
                    }
                ],
            )
            return {"ok": True}

        lat = message["latitude"]
        lng = message["longitude"]

        # Nearby Search
        result = await search_nearby(
            lat=lat,
            lng=lng,
            q="ラーメン",
            radius=1000,
        )

        raw_items = (result.get("results") or [])[:10]
        if not raw_items:
            await line_push(
                user_id,
                [
                    {
                        "type": "text",
                        "text": "近くにラーメン屋が見つからなかったよ…🍜",
                    }
                ],
            )
            user_states[user_id] = WAITING_NONE
            return {"ok": True}

        # Googleの result → Flex用item に変換
        items = []
        for r in raw_items:
            loc = (r.get("geometry") or {}).get("location") or {}
            if not loc.get("lat") or not loc.get("lng"):
                continue

            items.append(
                {
                    "name": r.get("name"),
                    "vicinity": r.get("vicinity"),
                    "lat": loc["lat"],
                    "lng": loc["lng"],
                    "open_now": (r.get("opening_hours") or {}).get("open_now"),
                    "rating": r.get("rating"),
                    "rating_count": r.get("user_ratings_total"),
                    "photo_reference": (
                        (r.get("photos") or [{}])[0].get("photo_reference")
                    ),
                }
            )
        flex = build_flex_carousel(items)
        await line_push(user_id, [flex])

        # ステート初期化
        user_states[user_id] = WAITING_NONE
        return {"ok": True}

    return {"ok": True}
