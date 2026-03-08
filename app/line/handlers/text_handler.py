from app.line.messages import build_preference_menu_flex
from app.line.state import WAITING_LOCATION, set_user_state
from app.services.line_client import line_push
from app.services.preference_service import get_preference_weights


async def handle_text_message(
    user_id: str,
    message: dict[str, object],
) -> None:
    text = str(message.get("text", "")).strip()

    if "好み" in text:
        weights = get_preference_weights(user_id)
        await line_push(user_id, [build_preference_menu_flex(weights)])
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