WAITING_NONE = "none"
WAITING_LOCATION = "waiting_location"

_user_states: dict[str, str] = {}


def get_user_state(user_id: str) -> str:
    return _user_states.get(user_id, WAITING_NONE)


def set_user_state(user_id: str, state: str) -> None:
    _user_states[user_id] = state


def clear_user_state(user_id: str) -> None:
    _user_states[user_id] = WAITING_NONE