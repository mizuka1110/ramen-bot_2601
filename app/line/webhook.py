from fastapi import APIRouter, Request
import logging

from app.services.places import search_nearby, nearby_result_to_items
from app.services.line_client import line_push
from app.line.messages import build_flex_carousel

# ===== cache add =====
from app.services.places_cache import get_cached, set_cached
# =====================

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
        # 先に「ラーメン」って言ってない人は誘導
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

        q = "ラーメン"
        radius = 1000

        # ===== cache add =====
        # まずキャッシュを見る（あればAPIを呼ばない）
        cached = get_cached(lat, lng, q, radius)
        # =====================

        # Nearby Search
        try:
            # ===== cache add =====
            if cached is not None:
                result = cached
            else:
                result = await search_nearby(
                    lat=lat,
                    lng=lng,
                    q=q,
                    radius=radius,
                )
                # 取得できたらキャッシュに保存
                set_cached(lat, lng, q, radius, result)
            # =====================
        except Exception:
            # ===== cache add =====
            # APIが落ちた/失敗したとき、キャッシュがあればそれを使う（保険）
            if cached is not None:
                result = cached
            else:
                await line_push(
                    user_id,
                    [
                        {
                            "type": "text",
                            "text": "今ちょっと検索できないみたい🙏 時間が経ってから試してね🙏",
                        }
                    ],
                )
                user_states[user_id] = WAITING_NONE
                return {"ok": True}
            # =====================

        # items を作る（distance_m 入る）
        items = nearby_result_to_items(result, user_lat=lat, user_lng=lng, limit=10)

        if not items:
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

        flex = build_flex_carousel(items)
        await line_push(user_id, [flex])

        # ステート初期化
        user_states[user_id] = WAITING_NONE
        return {"ok": True}

    # =========================
    # ③ 想定外イベント
    # =========================
    # sticker / image などが来たとき
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
