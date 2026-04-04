import os
import re

from app.services.preference_service import PREFERENCE_CATEGORIES


def _open_label(open_now: bool | None) -> tuple[str, str]:
    if open_now is True:
        return ("営業中", "#16A34A")
    if open_now is False:
        return ("時間外", "#6B7280")
    return ("不明", "#6B7280")


def _short_vicinity(vicinity: str | None) -> str:
    """
    住所を短縮する。
    - 丁目がある場合: 「◯丁目」までに短縮
      例: 渋谷区神南1丁目19-11 → 渋谷区神南1丁目
    - 丁目がない場合: 番地（数字・全角数字・ハイフン）を除去
      例: 柏市篠籠田９６９－１ → 柏市篠籠田
    """
    if not vicinity:
        return ""

    # 丁目がある場合は丁目までで切る
    m = re.match(r"^(.*?\d+丁目)", vicinity)
    if m:
        return m.group(1)

    # 丁目がない場合は番地部分を除去
    # 最初に登場する半角・全角数字以降を全て削除
    shortened = re.sub(r"[\d０-９].*$", "", vicinity).strip()
    return shortened if shortened else vicinity


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


def _build_meta(vicinity: str, distance_m: int | None) -> str | None:
    """
    住所と距離を組み合わせたメタ文字列を返す。
    どちらも無い場合は None を返す。
    """
    parts = []
    if vicinity:
        parts.append(vicinity)
    if distance_m is not None:
        parts.append(f"{distance_m}m")
    return "｜".join(parts) if parts else None


def _weight_status(value: float) -> tuple[str, str]:
    if value >= 100:
        return ("中毒", "#7C3AED")
    if value >= 0.5:
        return ("めちゃ好き", "#DC2626")
    if value >= 0.25:
        return ("好き", "#EA580C")
    if value <= -0.25:
        return ("苦手", "#2563EB")
    return ("未登録", "#6B7280")


def _build_preference_status_chip(value: float) -> dict:
    label, color = _weight_status(value)
    return {
        "type": "box",
        "layout": "horizontal",
        "contents": [
            {
                "type": "text",
                "text": label,
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
        "backgroundColor": color,
        "cornerRadius": "8px",
        "paddingAll": "4px",
        "paddingStart": "8px",
        "paddingEnd": "8px",
        "flex": 0,
    }


def _build_preference_category_box(category_key: str, label: str, current_value: float) -> dict:
    return {
        "type": "box",
        "layout": "vertical",
        "spacing": "sm",
        "paddingAll": "12px",
        "backgroundColor": "#FFFFFF",
        "cornerRadius": "16px",
        "borderWidth": "1px",
        "borderColor": "#E5E7EB",
        "width": "48%",
        "action": {
            "type": "postback",
            "label": label,
            "data": f"pref:category:{category_key}",
            "displayText": f"{label}を登録する",
        },
        "contents": [
            {
                "type": "text",
                "text": label,
                "weight": "bold",
                "size": "md",
                "wrap": True,
                "color": "#111827",
            },
            _build_preference_status_chip(current_value),
        ],
    }


def build_preference_menu_flex(weights: dict[str, float] | None = None) -> dict:
    weights = weights or {}
    items = list(PREFERENCE_CATEGORIES.items())

    rows: list[dict] = []
    for i in range(0, len(items), 2):
        left_key, left_label = items[i]
        left_box = _build_preference_category_box(
            category_key=left_key,
            label=left_label,
            current_value=weights.get(left_key, 0),
        )

        row_contents = [left_box]

        if i + 1 < len(items):
            right_key, right_label = items[i + 1]
            right_box = _build_preference_category_box(
                category_key=right_key,
                label=right_label,
                current_value=weights.get(right_key, 0),
            )
            row_contents.append(right_box)
        else:
            row_contents.append(
                {
                    "type": "box",
                    "layout": "vertical",
                    "width": "48%",
                    "contents": [],
                }
            )

        rows.append(
            {
                "type": "box",
                "layout": "horizontal",
                "spacing": "md",
                "contents": row_contents,
            }
        )

    return {
        "type": "flex",
        "altText": "好みを登録する",
        "contents": {
            "type": "bubble",
            "size": "giga",
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "md",
                "contents": [
                    {
                        "type": "text",
                        "text": "好みを登録する",
                        "weight": "bold",
                        "size": "xl",
                        "color": "#111827",
                    },
                    {
                        "type": "text",
                        "text": "気になる項目を押して登録してね",
                        "size": "sm",
                        "color": "#6B7280",
                        "wrap": True,
                    },
                    *rows,
                ],
            },
        },
    }


def build_preference_choice_flex(category: str, current_value: float = 0) -> dict:
    label = PREFERENCE_CATEGORIES.get(category, category)

    return {
        "type": "flex",
        "altText": f"{label}の好みを登録する",
        "contents": {
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "md",
                "contents": [
                    {
                        "type": "text",
                        "text": f"{label}はどれくらい好き？",
                        "weight": "bold",
                        "size": "lg",
                        "wrap": True,
                    },
                    {
                        "type": "text",
                        "text": "登録するとランキングに反映されます",
                        "size": "sm",
                        "color": "#6B7280",
                        "wrap": True,
                    },
                    _build_preference_status_chip(current_value),
                ],
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "spacing": "sm",
                "contents": [
                    {
                        "type": "button",
                        "style": "primary",
                        "height": "sm",
                        "color": "#7C3AED",
                        "action": {
                            "type": "postback",
                            "label": "中毒",
                            "data": f"pref:set:{category}:addict",
                            "displayText": f"{label}を中毒で登録",
                        },
                    },
                    {
                        "type": "button",
                        "style": "primary",
                        "height": "sm",
                        "color": "#DC2626",
                        "action": {
                            "type": "postback",
                            "label": "めちゃ好き",
                            "data": f"pref:set:{category}:love",
                            "displayText": f"{label}をめちゃ好きで登録",
                        },
                    },
                    {
                        "type": "button",
                        "style": "secondary",
                        "height": "sm",
                        "action": {
                            "type": "postback",
                            "label": "好き",
                            "data": f"pref:set:{category}:like",
                            "displayText": f"{label}を好きで登録",
                        },
                    },
                    {
                        "type": "button",
                        "style": "secondary",
                        "height": "sm",
                        "action": {
                            "type": "postback",
                            "label": "苦手",
                            "data": f"pref:set:{category}:dislike",
                            "displayText": f"{label}を苦手で登録",
                        },
                    },
                ],
            },
        },
    }


def build_okawari_message(next_offset: int) -> dict:
    return {
        "type": "text",
        "text": "続きのランキングも見る？",
        "quickReply": {
            "items": [
                {
                    "type": "action",
                    "action": {
                        "type": "postback",
                        "label": "おかわり🍜",
                        "data": f"ramen:more:{next_offset}",
                        "displayText": "おかわり🍜",
                    },
                }
            ]
        },
    }


def build_search_radius_message(radius_m: int) -> dict:
    return {
        "type": "text",
        "text": f"{radius_m}mまで検索しました🍜",
    }


def shop_to_bubble(
    item: dict,
    show_business_hours: bool = False,
    datetime_notice_text: str | None = None,
) -> dict:
    place_url = f"https://www.google.com/maps/place/?q=place_id:{item['place_id']}"
    label_text, label_bg = _open_label(item.get("open_now"))

    vicinity = _short_vicinity(item.get("vicinity"))
    distance_m = item.get("distance_m")
    meta = _build_meta(vicinity, distance_m)

    rating = item.get("rating")
    rating_count = item.get("rating_count")
    rating_text = None
    if rating is not None:
        rating_text = f"★{rating}"
        if rating_count is not None:
            rating_text += f"（{rating_count}）"

    map_url = place_url

    business_hours_text = item.get("business_hours_text")
    status_contents: list[dict] = [
        {
            "type": "box",
            "layout": "horizontal",
            "contents": [
                {
                    "type": "text",
                    "text": label_text,
                    "size": "xs",
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
            "cornerRadius": "8px",
            "paddingAll": "4px",
            "paddingStart": "10px",
            "paddingEnd": "10px",
            "flex": 0,
            "maxWidth": "58px",
        },
    ]
    if show_business_hours and isinstance(business_hours_text, str) and business_hours_text.strip():
        status_contents.append(
            {
                "type": "text",
                "text": business_hours_text,
                "size": "xs",
                "color": "#6B7280",
                "flex": 0,
                "margin": "sm",
            }
        )
        if isinstance(datetime_notice_text, str) and datetime_notice_text.strip():
            status_contents.append(
                {
                    "type": "text",
                    "text": datetime_notice_text,
                    "size": "xxs",
                    "color": "#9CA3AF",
                    "wrap": True,
                    "flex": 0,
                    "margin": "xs",
                }
            )

    body_contents = [
        {
            "type": "box",
            "layout": "vertical",
            "alignItems": "flex-start",
            "contents": status_contents,
        },
        {
            "type": "text",
            "text": item.get("name") or "-",
            "weight": "bold",
            "size": "lg",
            "wrap": True,
        },
    ]

    # 住所・距離は存在する場合のみ追加
    if meta:
        body_contents.append(
            {
                "type": "text",
                "text": meta,
                "size": "sm",
                "color": "#6B7280",
                "wrap": True,
            }
        )

    if rating_text:
        body_contents.append(
            {
                "type": "text",
                "text": rating_text,
                "size": "sm",
                "color": "#111827",
                "wrap": True,
                "margin": "md",
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
            "aspectRatio": "16:9",
            "aspectMode": "cover",
            "action": {
                "type": "uri",
                "uri": place_url,
            },
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
            "paddingTop": "4px",
            "paddingBottom": "12px",
            "alignItems": "center",
            "contents": [
                {
                    "type": "box",
                    "layout": "horizontal",
                    "margin": "md",
                    "alignItems": "center",
                    "justifyContent": "center",
                    "spacing": "xs",
                    "action": {
                        "type": "uri",
                        "uri": map_url,
                    },
                    "contents": [
                        {
                            "type": "image",
                            "url": f"{(os.getenv('PUBLIC_BASE_URL') or '').rstrip('/')}/static/pin.png",
                            "size": "16px",
                            "flex": 0,
                        },
                        {
                            "type": "text",
                            "text": "地図を開く",
                            "size": "sm",
                            "color": "#2563EB",
                            "flex": 0,
                        },
                    ],
                }
            ],
        },
    }


def build_flex_carousel(
    items: list[dict],
    show_business_hours: bool = False,
    datetime_notice_text: str | None = None,
) -> dict:
    # 念のため None 混入を防ぐ（shop_to_bubbleは基本None返さない想定）
    bubbles = [
        b
        for b in (
            shop_to_bubble(
                x,
                show_business_hours=show_business_hours,
                datetime_notice_text=datetime_notice_text,
            )
            for x in (items or [])[:10]
        )
        if b
    ]

    return {
        "type": "flex",
        "altText": "近くのラーメン店",
        "contents": {
            "type": "carousel",
            "contents": bubbles,
        },
    }
