WAITING_NONE = "none"
WAITING_LOCATION = "waiting_location"

_user_states: dict[str, str] = {}
_user_search_sessions: dict[str, dict[str, float | int | str]] = {}
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
) -> None:
    _user_search_sessions[user_id] = {
        "lat": lat,
        "lng": lng,
        "next_offset": next_offset,
    }
    if search_datetime is not None:
        _user_search_sessions[user_id]["search_datetime"] = search_datetime


def get_search_session(user_id: str) -> dict[str, float | int | str] | None:
    return _user_search_sessions.get(user_id)


def clear_search_session(user_id: str) -> None:
    _user_search_sessions.pop(user_id, None)


def set_user_datetime(user_id: str, search_datetime: str) -> None:
    _user_datetime_sessions[user_id] = search_datetime


def get_user_datetime(user_id: str) -> str | None:
    return _user_datetime_sessions.get(user_id)


def clear_user_datetime(user_id: str) -> None:
    _user_datetime_sessions.pop(user_id, None)