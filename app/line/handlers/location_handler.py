from app.line.messages import (
    build_flex_carousel,
    build_okawari_message,
    build_search_radius_message,
)
from app.line.state import (
    WAITING_LOCATION,
    clear_search_session,
    clear_user_state,
    get_user_state,
    set_search_session,
)
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
                    "text": "現在、直接の位置送信には対応しておりません🍜",
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

    items, had_error, has_more, used_radius = await search_ramen_items(
        lat=lat,
        lng=lng,
        line_user_id=user_id,
        offset=0,
        page_size=10,
    )

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
                        "text": "3000m以内にラーメン屋さんが見つかりません…🍜",
                    }
                ],
            )

        clear_user_state(user_id)
        return

    flex = build_flex_carousel(items)
    messages: list[dict] = [flex]
    if used_radius is not None:
        messages.append(build_search_radius_message(used_radius))

    if has_more:
        set_search_session(user_id, lat=lat, lng=lng, next_offset=10)
        messages.append(build_okawari_message(next_offset=10))
    else:
        clear_search_session(user_id)

    await line_reply(reply_token, messages)

    clear_user_state(user_id)