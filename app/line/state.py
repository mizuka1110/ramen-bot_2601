WAITING_NONE = "none"
WAITING_LOCATION = "waiting_location"

_user_states: dict[str, str] = {}
_user_search_sessions: dict[str, dict[str, float | int]] = {}


def get_user_state(user_id: str) -> str:
    return _user_states.get(user_id, WAITING_NONE)


def set_user_state(user_id: str, state: str) -> None:
    _user_states[user_id] = state


def clear_user_state(user_id: str) -> None:
    _user_states[user_id] = WAITING_NONE


def set_search_session(user_id: str, lat: float, lng: float, next_offset: int) -> None:
    _user_search_sessions[user_id] = {
        "lat": lat,
        "lng": lng,
        "next_offset": next_offset,
    }


def get_search_session(user_id: str) -> dict[str, float | int] | None:
    return _user_search_sessions.get(user_id)


def clear_search_session(user_id: str) -> None:
    _user_search_sessions.pop(user_id, None)