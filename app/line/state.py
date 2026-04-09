WAITING_NONE = "none"
WAITING_LOCATION = "waiting_location"

_user_states: dict[str, str] = {}
_user_search_sessions: dict[str, dict[str, float | int | str | bool | list[dict]]] = {}
_user_datetime_sessions: dict[str, str] = {}


def get_user_state(user_id: str) -> str:
    return _user_states.get(user_id, WAITING_NONE)


def set_user_state(user_id: str, state: str) -> None:
    _user_states[user_id] = state


def clear_user_state(user_id: str) -> None:
    _user_states[user_id] = WAITING_NONE


def set_search_session(
    user_id: str,
    lat: float,
    lng: float,
    next_offset: int,
    search_datetime: str | None = None,
    prefetched_items: list[dict] | None = None,
    has_more_after_prefetch: bool | None = None,
) -> None:
    _user_search_sessions[user_id] = {
        "lat": lat,
        "lng": lng,
        "next_offset": next_offset,
    }
    if search_datetime is not None:
        _user_search_sessions[user_id]["search_datetime"] = search_datetime
    if prefetched_items is not None:
        _user_search_sessions[user_id]["prefetched_items"] = prefetched_items
    if has_more_after_prefetch is not None:
        _user_search_sessions[user_id]["has_more_after_prefetch"] = has_more_after_prefetch


def get_search_session(user_id: str) -> dict[str, float | int | str | bool | list[dict]] | None:
    return _user_search_sessions.get(user_id)


def clear_search_session(user_id: str) -> None:
    _user_search_sessions.pop(user_id, None)


def set_user_datetime(user_id: str, search_datetime: str) -> None:
    _user_datetime_sessions[user_id] = search_datetime


def get_user_datetime(user_id: str) -> str | None:
    return _user_datetime_sessions.get(user_id)


def clear_user_datetime(user_id: str) -> None:
    _user_datetime_sessions.pop(user_id, None)