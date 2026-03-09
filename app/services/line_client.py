import httpx
import os

LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"
LINE_REPLY_URL = "https://api.line.me/v2/bot/message/reply"
LINE_LOADING_URL = "https://api.line.me/v2/bot/chat/loading/start"


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


async def line_reply(reply_token: str, messages: list[dict]) -> None:
    token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
    if not token:
        raise LinePushError("LINE_CHANNEL_ACCESS_TOKEN is empty")

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "replyToken": reply_token,
        "messages": messages,
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        res = await client.post(LINE_REPLY_URL, headers=headers, json=payload)

    if res.status_code >= 400:
        raise LinePushError(f"LINE reply failed: {res.status_code} {res.text}")


async def line_loading(user_id: str, seconds: int = 20) -> None:
    """
    LINEのローディングアニメーションを表示する。
    seconds: 表示秒数（5〜60、5の倍数）
    エラーは握り潰す（ローディングが出なくても致命的ではないため）
    """
    token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
    if not token:
        return

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {"chatId": user_id, "loadingSeconds": seconds}

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(LINE_LOADING_URL, headers=headers, json=payload)
    except Exception:
        pass