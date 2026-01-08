from fastapi import APIRouter, Request
import logging

from app.services.places import search_nearby, nearby_result_to_items, get_place_reviews
from app.services.ai_summary import summarize_reviews_30
from app.services.line_client import line_push
from app.line.messages import build_flex_carousel

from app.services.places_cache import get_cached, set_cached

router = APIRouter()
logger = logging.getLogger("uvicorn.error")

WAITING_NONE = "none"
WAITING_LOCATION = "waiting_location"

user_states: dict[str, str] = {}


@router.post("/line/webhook")
async def line_webhook(request: Request):
    body = await request.json()
    logger.info("LINE webhook payload received")

    events = body.get("events", [])
    if not events:
        return {"ok": True}

    event = events[0]
    user_id = event["source"]["userId"]
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

        await line_push(
            user_id,
            [{"type": "text", "text": "「近くのラーメン」って送ってみて🍜"}],
        )
        return {"ok": True}

    # =========================
    # ② 位置情報イベント
    # =========================
    if message.get("type") == "location":
        if state != WAITING_LOCATION:
            await line_push(
                user_id,
                [{"type": "text", "text": "先に「近くのラーメン」って送ってね🍜"}],
            )
            return {"ok": True}

        lat = message["latitude"]
        lng = message["longitude"]

        q = "ラーメン"
        items = []
        had_error = False

        for radius in (1000, 2000, 3000):
            cached = get_cached(lat, lng, q, radius)

            try:
                if cached:
                    result = cached
                else:
                    result = await search_nearby(lat=lat, lng=lng, q=q, radius=radius)
                    set_cached(lat, lng, q, radius, result)
            except Exception:
                had_error = True
                if cached:
                    result = cached
                else:
                    continue

            items = nearby_result_to_items(result, user_lat=lat, user_lng=lng, limit=10)
            if items:
                break

        if not items:
            if had_error:
                await line_push(
                    user_id,
                    [{"type": "text", "text": "今ちょっと検索できないみたい🙏"}],
                )
            else:
                await line_push(
                    user_id,
                    [{"type": "text", "text": "近くにラーメン屋が見つからなかったよ…🍜"}],
                )
            user_states[user_id] = WAITING_NONE
            return {"ok": True}


        # =========================
        # ③ AI 口コミ要約（先頭3件だけ）
        # =========================
        for item in items[:3]:
            try:
                place_id = item.get("place_id")
                logger.info("AI summary start place_id=%s", place_id)

                if not place_id:
                    continue

                reviews = await get_place_reviews(place_id)
                logger.info("reviews_count=%d", len(reviews))

                summary = await summarize_reviews_30(reviews)
                if summary:
                    item["review_summary"] = summary

            except Exception as e:
                logger.exception("AI summary failed place_id=%s: %s", place_id, e)


        # =========================
        # ④ カルーセル送信
        # =========================
        flex = build_flex_carousel(items)
        await line_push(user_id, [flex])

        user_states[user_id] = WAITING_NONE
        return {"ok": True}

    # =========================
    # ③ 想定外イベント
    # =========================
    await line_push(
        user_id,
        [{"type": "text", "text": "「近くのラーメン」って送ってみて🍜"}],
    )
    return {"ok": True}
