import os

def _open_label(open_now: bool | None) -> tuple[str, str]:
    if open_now is True:
        return ("営業中", "#16A34A")
    if open_now is False:
        return ("時間外", "#6B7280")
    return ("不明", "#6B7280")


def _photo_url(photo_reference: str | None, maxwidth: int = 600) -> str:
    """
    LINEが取りにいけるURLを返す必要がある。
    PUBLIC_BASE_URL が未設定の場合は、とりあえずプレースホルダー。
    """
    base = (os.getenv("PUBLIC_BASE_URL") or "").rstrip("/")

    if photo_reference and base:
        return f"{base}/shops/photo?ref={photo_reference}&maxwidth={maxwidth}"

    if base:
        return f"{base}/static/no-image.jpg"

    # base が無い = LINEが見に行けるURLが作れないのでプレースホルダー
    return "https://via.placeholder.com/600x338?text=No+Image"


def shop_to_bubble(item: dict) -> dict:
    label_text, label_bg = _open_label(item.get("open_now"))

    vicinity = item.get("vicinity") or ""
    distance_m = item.get("distance_m")
    meta = f"{vicinity}｜{distance_m}m" if distance_m is not None else vicinity

    rating = item.get("rating")
    rating_count = item.get("rating_count")
    rating_text = None
    if rating is not None:
        rating_text = f"★{rating}"
        if rating_count is not None:
            rating_text += f"（{rating_count}）"

    lat = item.get("lat")
    lng = item.get("lng")

    map_url = (
        f"https://www.google.com/maps/search/?api=1&query={lat},{lng}"
        if lat is not None and lng is not None
        else (item.get("maps_url") or "https://www.google.com/maps")
    )

    body_contents = [
        {
            "type": "box",
            "layout": "horizontal",
            "contents": [
                {
                    "type": "text",
                    "text": label_text,
                    "size": "xxs",
                    "weight": "bold",
                    "color": "#FFFFFF",
                    "align": "center",
                    "gravity": "center",
                    "flex": 0,
                }
            ],
            "justifyContent": "center",
            "alignItems": "center",
            "backgroundColor": label_bg,
            "cornerRadius": "999px",
            "paddingAll": "4px",
            "paddingStart": "10px",
            "paddingEnd": "10px",
            "flex": 0,
            "maxWidth": "55px",
        },
        {
            "type": "text",
            "text": item.get("name") or "-",
            "weight": "bold",
            "size": "lg",
            "wrap": True,
        },
        {
            "type": "text",
            "text": meta,
            "size": "sm",
            "color": "#6B7280",
            "wrap": True,
        },
    ]

    if rating_text:
        body_contents.append(
            {
                "type": "text",
                "text": rating_text,
                "size": "sm",
                "color": "#111827",
                "wrap": True,
            }
        )

    summary = item.get("review_summary")
    if summary:
        body_contents.append(
            {
                "type": "text",
                "text": summary,
                "size": "sm",
                "color": "#374151",
                "wrap": True,
            }
        )

    return {
        "type": "bubble",
        "hero": {
            "type": "image",
            "url": _photo_url(item.get("photo_reference")),
            "size": "full",
            "aspectRatio": "16:9",  # ← 縦長すぎ対策
            "aspectMode": "cover",
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": body_contents,
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": [
                {
                    "type": "button",
                    "style": "secondary",
                    "action": {
                        "type": "uri",
                        "label": "地図アプリを開く ",
                        "uri": map_url,
                    },
                }
            ],
        },
    }


def build_flex_carousel(items: list[dict]) -> dict:
    # 念のため None 混入を防ぐ（shop_to_bubbleは基本None返さない想定）
    bubbles = [b for b in (shop_to_bubble(x) for x in (items or [])[:10]) if b]

    return {
        "type": "flex",
        "altText": "近くのラーメン店",
        "contents": {
            "type": "carousel",
            "contents": bubbles,
        },
    }
