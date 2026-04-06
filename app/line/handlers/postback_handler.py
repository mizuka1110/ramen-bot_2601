from app.line.messages import (
    build_flex_carousel,
    build_okawari_message,
    build_preference_choice_flex,
    build_preference_menu_flex,
)
from app.line.state import clear_search_session, get_search_session, set_search_session
from app.services.line_client import line_loading, line_reply
from app.services.preference_service import (
    PREFERENCE_CATEGORIES,
    get_preference_choice_label,
    get_preference_weights,
    set_preference,
)
from app.services.ramen_search import search_ramen_items


async def handle_postback(
    user_id: str,
    reply_token: str | None,
    postback: dict[str, object],
) -> None:
    if not reply_token:
        return

    data = str(postback.get("data", ""))

    if data.startswith("ramen:more:"):
        parts = data.split(":")
        if len(parts) != 3:
            await line_reply(
                reply_token,
                [{"type": "text", "text": "おかわりをうまく読み取れなかったよ🙏"}],
            )
            return

        session = get_search_session(user_id)
        if not session:
            await line_reply(
                reply_token,
                [{"type": "text", "text": "先に現在地からラーメン検索してね🍜"}],
            )
            return

        lat = session.get("lat")
        lng = session.get("lng")
        offset = session.get("next_offset")
        search_datetime = session.get("search_datetime")
        if not isinstance(lat, float) or not isinstance(lng, float) or not isinstance(offset, int):
            clear_search_session(user_id)
            await line_reply(
                reply_token,
                [{"type": "text", "text": "検索状態が切れたので、もう一度現在地を送ってね🙏"}],
            )
            return
        
        await line_loading(user_id)

        items, had_error, has_more, _used_radius = await search_ramen_items(
            lat=lat,
            lng=lng,
            line_user_id=user_id,
            offset=offset,
            page_size=10,
            search_datetime=search_datetime if isinstance(search_datetime, str) else None,
        )
        if not items:
            if had_error:
                await line_reply(
                    reply_token,
                    [{"type": "text", "text": "今ちょっと検索できないみたい🙏"}],
                )
            else:
                await line_reply(
                    reply_token,
                    [{"type": "text", "text": "これ以上の候補は見つからなかったよ🍜"}],
                )
            clear_search_session(user_id)
            return

        messages: list[dict] = [
            build_flex_carousel(
                items,
                show_business_hours=False,
            )
        ]
        next_offset = offset + 10
        if has_more:
            set_search_session(
                user_id,
                lat=lat,
                lng=lng,
                next_offset=next_offset,
                search_datetime=search_datetime if isinstance(search_datetime, str) else None,
            )
            messages.append(build_okawari_message(next_offset=next_offset))
        else:
            clear_search_session(user_id)

        await line_reply(reply_token, messages)
        return

    if data == "pref:menu":
        weights = get_preference_weights(user_id)
        await line_reply(reply_token, [build_preference_menu_flex(weights)])
        return

    if data.startswith("pref:category:"):
        category = data.replace("pref:category:", "", 1)

        if category not in PREFERENCE_CATEGORIES:
            await line_reply(
                reply_token,
                [{"type": "text", "text": "カテゴリをうまく読み取れなかったよ🙏"}],
            )
            return

        weights = get_preference_weights(user_id)
        current_value = weights.get(category, 0)
        await line_reply(
            reply_token,
            [build_preference_choice_flex(category, current_value)],
        )
        return

    if data.startswith("pref:set:"):
        parts = data.split(":", 3)
        if len(parts) != 4:
            await line_reply(
                reply_token,
                [{"type": "text", "text": "登録処理をうまく読み取れなかったよ🙏"}],
            )
            return

        _, _, category, choice = parts

        try:
            weights = set_preference(user_id, category, choice)
        except ValueError:
            await line_reply(
                reply_token,
                [{"type": "text", "text": "登録内容をうまく読み取れなかったよ🙏"}],
            )
            return

        choice_label = get_preference_choice_label(choice)

        await line_reply(
            reply_token,
            [
                {
                    "type": "text",
                    "text": f"「{category}」を「{choice_label}」で登録したよ🍜",
                },
                build_preference_menu_flex(weights),
            ],
        )
        return

    await line_reply(
        reply_token,
        [{"type": "text", "text": "操作をうまく読み取れなかったよ🙏"}],
    )