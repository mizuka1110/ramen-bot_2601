from app.services.line_client import line_reply


async def handle_text_message(
    user_id: str,
    reply_token: str | None,
    message: dict[str, object],
) -> None:
    if not reply_token:
        return

    text = str(message.get("text", "")).strip()

    liff_base_url = "https://liff.line.me/2009360861-I31kIVzt"

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
        location_liff_url = f"{liff_base_url}/location"
        await line_reply(
            reply_token,
            [
                {
                    "type": "flex",
                    "altText": "現在地からラーメン検索",
                    "contents": {
                        "type": "bubble",
                        "body": {
                            "type": "box",
                            "layout": "vertical",
                            "spacing": "md",
                            "contents": [
                                {
                                    "type": "text",
                                    "text": "現在地からラーメン検索",
                                    "weight": "bold",
                                    "size": "lg",
                                },
                                {
                                    "type": "text",
                                    "text": "位置送信用LIFFを開いて、現在地を送信してね。",
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
                                        "label": "位置送信を開く",
                                        "uri": location_liff_url,
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
