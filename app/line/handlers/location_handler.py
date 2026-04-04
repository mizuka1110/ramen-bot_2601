from datetime import datetime
from urllib.parse import parse_qs

from app.line.messages import (
    build_flex_carousel,
    build_okawari_message,
    build_search_radius_message,
)
from app.line.state import (
    clear_search_session,
    clear_user_state,
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
    target_datetime_jst = _extract_target_datetime_jst(message)

    await handle_search_with_location(
        user_id=user_id,
        reply_token=reply_token,
        lat=lat,
        lng=lng,
        target_datetime_jst=target_datetime_jst,
    )


def _extract_target_datetime_jst(message: dict[str, object]) -> datetime | None:
    address_value = message.get("address")
    if not isinstance(address_value, str) or not address_value.strip():
        return None

    metadata = parse_qs(address_value, keep_blank_values=True)
    timezone = (metadata.get("timezone", [""])[0] or "").strip()
    datetime_str = (metadata.get("datetime", [""])[0] or "").strip()

    if not datetime_str:
        return None
    if timezone not in ("", "Asia/Tokyo"):
        return None

    try:
        return datetime.fromisoformat(datetime_str)
    except ValueError:
        return None


async def handle_search_with_location(
    user_id: str,
    reply_token: str,
    lat: float,
    lng: float,
    target_datetime_jst: datetime | None,
) -> None:

    await line_loading(user_id)

    items, had_error, has_more, used_radius = await search_ramen_items(
        lat=lat,
        lng=lng,
        line_user_id=user_id,
        offset=0,
        page_size=10,
        target_datetime_jst=target_datetime_jst,
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
                        "text": (
                            "指定日時に営業中のラーメン屋さんが見つかりませんでした…🍜"
                            if target_datetime_jst
                            else "3000m以内に営業中のラーメン屋さんが見つかりません…🍜"
                        ),
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
        set_search_session(
            user_id,
            lat=lat,
            lng=lng,
            next_offset=10,
            target_datetime_jst=target_datetime_jst.isoformat() if target_datetime_jst else None,
        )
        messages.append(build_okawari_message(next_offset=10))
    else:
        clear_search_session(user_id)

    await line_reply(reply_token, messages)

    clear_user_state(user_id)
