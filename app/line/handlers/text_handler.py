from app.services.line_client import line_reply
from app.config import PUBLIC_BASE_URL


async def handle_text_message(
    user_id: str,
    reply_token: str | None,
    message: dict[str, object],
) -> None:
    if not reply_token:
        return

    text = str(message.get("text", "")).strip()

    liff_base_url = "https://liff.line.me/2009360861-I31kIVzt"
    search_url = f"{PUBLIC_BASE_URL.rstrip('/')}/search" if PUBLIC_BASE_URL else "/search"

    if "好み" in text:
        preferences_url = liff_base_url

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
        await line_reply(
            reply_token,
            [
                {
                    "type": "flex",
                    "altText": "ラーメンを検索する",
                    "contents": {
                        "type": "bubble",
                        "body": {
                            "type": "box",
                            "layout": "vertical",
                            "spacing": "md",
                            "contents": [
                                {
                                    "type": "text",
                                    "text": "ラーメンを検索する",
                                    "weight": "bold",
                                    "size": "lg",
                                },
                                {
                                    "type": "text",
                                    "text": "検索メニューを開いて、現在地送信や場所指定で探してね。",
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
                                        "label": "検索メニューを開く",
                                        "uri": search_url,
                                    },
                                }
                            ],
                        },
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
