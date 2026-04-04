from datetime import datetime
from app.config import DATETIME_LIFF_ID, DATETIME_LIFF_URL, PUBLIC_BASE_URL
from app.line.state import WAITING_LOCATION, set_user_datetime, set_user_state
from app.services.line_client import line_reply


async def handle_text_message(
    user_id: str,
    reply_token: str | None,
    message: dict[str, object],
) -> None:
    if not reply_token:
        return

    text = str(message.get("text", "")).strip()

    if "日時・場所を指定" in text:
        datetime_url = DATETIME_LIFF_URL
        if not datetime_url and PUBLIC_BASE_URL:
            datetime_url = f"{PUBLIC_BASE_URL}/static/datetime.html"
        if not datetime_url and DATETIME_LIFF_ID:
            datetime_url = f"https://liff.line.me/{DATETIME_LIFF_ID}"
        await line_reply(
            reply_token,
            [
                {
                    "type": "flex",
                    "altText": "日時・場所を指定",
                    "contents": {
                        "type": "bubble",
                        "body": {
                            "type": "box",
                            "layout": "vertical",
                            "spacing": "md",
                            "contents": [
                                {
                                    "type": "text",
                                    "text": "日時・場所を指定",
                                    "weight": "bold",
                                    "size": "lg",
                                },
                                {
                                    "type": "text",
                                    "text": "設定した日時の情報を検索できます。",
                                    "wrap": True,
                                    "size": "sm",
                                    "color": "#666666",
                                },
                            ],
                        },
                        "footer": {
                            "type": "box",
                            "layout": "vertical",
                            "spacing": "sm",
                            "alignItems": "center",
                            "contents": [
                                {
                                    "type": "box",
                                    "layout": "vertical",
                                    "width": "70%",
                                    "contents": [
                                        {
                                            "type": "button",
                                            "style": "primary",
                                            "height": "sm",
                                            "color": "#ff8c3a",
                                            "action": {
                                                "type": "uri",
                                                "label": "日時を選ぶ",
                                                "uri": datetime_url,
                                            },
                                        }
                                    ],
                                }
                            ],
                        },
                    },
                }
            ],
        )
        return

    if text.startswith("日時指定:"):
        raw_datetime = text.replace("日時指定:", "", 1).strip()
        try:
            parsed = datetime.fromisoformat(raw_datetime)
        except ValueError:
            await line_reply(
                reply_token,
                [{"type": "text", "text": "日時をうまく読み取れなかったよ🙏"}],
            )
            return

        set_user_datetime(user_id, parsed.isoformat(timespec="minutes"))
        set_user_state(user_id, WAITING_LOCATION)
        await line_reply(
            reply_token,
            [
                {
                    "type": "text",
                    "text": "位置情報を送ってください📍",
                    "quickReply": {
                        "items": [
                            {
                                "type": "action",
                                "action": {
                                    "type": "location",
                                    "label": "現在地を送る",
                                },
                            }
                        ]
                    },
                }
            ],
        )
        return

    if "好み" in text:
        preferences_url = "https://liff.line.me/2009360861-I31kIVzt"

        await line_reply(
            reply_token,
            [
                {
                    "type": "flex",
                    "altText": "好みを登録",
                    "contents": {
                        "type": "bubble",
                        "body": {
                            "type": "box",
                            "layout": "vertical",
                            "spacing": "md",
                            "contents": [
                                {
                                    "type": "text",
                                    "text": "ラーメンの好みを登録",
                                    "weight": "bold",
                                    "size": "lg",
                                },
                                {
                                    "type": "text",
                                    "text": "好みを登録すると、検索結果に反映されます。",
                                    "wrap": True,
                                    "size": "sm",
                                    "color": "#666666",
                                },
                            ],
                        },
                        "footer": {
                            "type": "box",
                            "layout": "vertical",
                            "spacing": "sm",
                            "alignItems": "center",
                            "contents": [
                                {
                                    "type": "button",
                                    "style": "primary",
                                    "height": "sm",
                                    "color": "#ff8c3a",
                                    "action": {
                                        "type": "uri",
                                        "label": "好みを登録する",
                                        "uri": preferences_url,
                                    },
                                }
                            ],
                        }
                    },
                }
            ],
        )
        return

    if "ラーメン" in text:
        set_user_state(user_id, WAITING_LOCATION)
        await line_reply(
            reply_token,
            [
                {
                    "type": "text",
                    "text": "了解！\n\n下のボタンから現在地を送ってね",
                    "quickReply": {
                        "items": [
                            {
                                "type": "action",
                                "action": {
                                    "type": "location",
                                    "label": "現在地を送る",
                                },
                            }
                        ]
                    },
                }
            ],
        )
        return

    await line_reply(
        reply_token,
        [
            {
                "type": "text",
                "text": "「ラーメン食べたい」か「好みを登録」って送ってみて🍜",
            }
        ],
    )
