from datetime import datetime, timezone

from app.line.messages import (
    build_flex_carousel,
    build_okawari_message,
    build_search_radius_message,
)
from app.line.state import (
    clear_search_session,
    clear_user_state,
    get_user_datetime,
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
    selected_datetime = get_user_datetime(user_id)
    search_datetime = selected_datetime or datetime.now(timezone.utc).isoformat(timespec="minutes")

    await line_loading(user_id)

    items, had_error, has_more, used_radius = await search_ramen_items(
        lat=lat,
        lng=lng,
        line_user_id=user_id,
        offset=0,
        page_size=10,
        search_datetime=search_datetime,
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

    datetime_notice_message: dict | None = None
    if selected_datetime:
        try:
            target = datetime.fromisoformat(selected_datetime)
            timestamp_label = f"{target.month}月{target.day}日{target.hour}時{target.minute:02d}分"
        except ValueError:
            timestamp_label = selected_datetime
        datetime_notice_message = {
            "type": "text",
            "text": f"※{timestamp_label}時点の営業情報です。実際の状況と異なる場合があります。",
        }

    flex = build_flex_carousel(
        items,
        show_business_hours=selected_datetime is not None,
    )
    messages: list[dict] = []
    messages.append(flex)
    if datetime_notice_message:
        messages.append(datetime_notice_message)
    if used_radius is not None and used_radius >= 2000:
        messages.append(build_search_radius_message(used_radius))

    if selected_datetime:
        messages.append(
            {
                "type": "text",
                "text": "同じ時間の別の場所で検索しますか？",
                "quickReply": {
                    "items": [
                        {
                            "type": "action",
                            "action": {
                                "type": "location",
                                "label": "別の地点で検索する",
                            },
                        }
                    ]
                },
            }
        )
        clear_search_session(user_id)
    elif has_more:
        set_search_session(
            user_id,
            lat=lat,
            lng=lng,
            next_offset=10,
            search_datetime=search_datetime,
        )
        messages.append(build_okawari_message(next_offset=10))
    else:
        clear_search_session(user_id)

    await line_reply(reply_token, messages)

    clear_user_state(user_id)