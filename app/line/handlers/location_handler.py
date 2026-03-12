from app.line.messages import build_flex_carousel
from app.line.state import WAITING_LOCATION, clear_user_state, get_user_state
from app.services.line_client import line_loading, line_reply
from app.services.ramen_search import search_ramen_items


async def handle_location_message(
    user_id: str,
    reply_token: str | None,
    message: dict[str, object],
) -> None:
    if not reply_token:
        return

    state = get_user_state(user_id)

    if state != WAITING_LOCATION:
        await line_reply(
            reply_token,
            [
                {
                    "type": "text",
                    "text": "先に「ラーメン」って送ってね🍜",
                }
            ],
        )
        return

    lat_value = message.get("latitude")
    lng_value = message.get("longitude")

    if not isinstance(lat_value, (int, float)) or not isinstance(
        lng_value, (int, float)
    ):
        await line_reply(
            reply_token,
            [
                {
                    "type": "text",
                    "text": "位置情報をうまく受け取れなかったよ🙏",
                }
            ],
        )
        clear_user_state(user_id)
        return

    lat = float(lat_value)
    lng = float(lng_value)

    await line_loading(user_id)

    items, had_error = await search_ramen_items(lat=lat, lng=lng)

    if not items:
        if had_error:
            await line_reply(
                reply_token,
                [
                    {
                        "type": "text",
                        "text": "今ちょっと検索できないみたい🙏",
                    }
                ],
            )
        else:
            await line_reply(
                reply_token,
                [
                    {
                        "type": "text",
                        "text": "近くにラーメン屋が見つからなかったよ…🍜",
                    }
                ],
            )

        clear_user_state(user_id)
        return

    flex = build_flex_carousel(items)
    await line_reply(reply_token, [flex])

    clear_user_state(user_id)