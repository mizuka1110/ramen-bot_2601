import httpx
import os

LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"


class LinePushError(Exception):
    pass


async def line_push(to_user_id: str, messages: list[dict]) -> None:
    token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
    if not token:
        raise LinePushError("LINE_CHANNEL_ACCESS_TOKEN is empty")

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {"to": to_user_id, "messages": messages}

    async with httpx.AsyncClient(timeout=10.0) as client:
        res = await client.post(LINE_PUSH_URL, headers=headers, json=payload)

    if res.status_code >= 400:
        raise LinePushError(f"LINE push failed: {res.status_code} {res.text}")
