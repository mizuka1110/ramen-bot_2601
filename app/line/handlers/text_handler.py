from app.config import PUBLIC_BASE_URL
from app.line.state import WAITING_LOCATION, set_user_state
from app.services.line_client import line_push


async def handle_text_message(
    user_id: str,
    message: dict[str, object],
) -> None:
    text = str(message.get("text", "")).strip()

    if "好み" in text:
        preferences_url = f"{PUBLIC_BASE_URL.rstrip('/')}/preferences"

        await line_push(
            user_id,
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
                            "contents": [
                                {
                                    "type": "button",
                                    "style": "primary",
                                    "color": "#ff8c3a",
                                    "action": {
                                        "type": "uri",
                                        "label": "好みを登録する",
                                        "uri": preferences_url,
                                    },
                                }
                            ],
                        },
                    },
                }
            ],
        )
        return

    if "ラーメン" in text:
        set_user_state(user_id, WAITING_LOCATION)
        await line_push(
            user_id,
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

    await line_push(
        user_id,
        [
            {
                "type": "text",
                "text": "「ラーメン食べたい」か「好みを登録」って送ってみて🍜",
            }
        ],
    )