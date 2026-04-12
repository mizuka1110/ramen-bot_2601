from typing import TypedDict

from openai import AsyncOpenAI

client = AsyncOpenAI()


class ReviewItem(TypedDict, total=False):
    text: str
    rating: int | float


async def summarize_reviews_30(reviews: list[ReviewItem]) -> str | None:
    texts = [
        r["text"].strip()
        for r in reviews
        if (r.get("rating") or 0) >= 4 and r.get("text")
    ][:5]

    if not texts:
        return None

    prompt = (
        "次の口コミを日本語で1文のみ、25字で要約して。"
        "主にラーメンの味に関するポジティブな内容を使って"
        "客観的な文体にし、ですますは使わない\n\n"
        + "\n".join(f"- {t}" for t in texts)
    )

    resp = await client.responses.create(
        model="gpt-4o-mini",
        input=prompt,
    )

    summary = (resp.output_text or "").strip()
    return summary or None


async def extract_ramen_categories(
    editorial_summary: str | None,
    reviews: list[ReviewItem],
) -> list[str]:
    review_texts = [
        r["text"].strip()
        for r in reviews
        if r.get("text")
    ][:5]

    source_text = "\n".join(
        part for part in [editorial_summary or "", *review_texts] if part
    ).strip()

    if not source_text:
        return []

    prompt = (
        "次のラーメン店の説明文・口コミから、該当するカテゴリのみを選んでください。\n"
        "候補: 魚介, 煮干し, 鶏白湯, 豚骨, 醤油, 味噌, 塩, 辛い, 家系, 二郎系\n"
        "出力は候補の中から該当するものだけを、カンマ区切りで1行で返してください。\n"
        "該当なしなら空文字で返してください。\n\n"
        f"{source_text}"
    )

    resp = await client.responses.create(
        model="gpt-4o-mini",
        input=prompt,
    )

    result = (resp.output_text or "").strip()
    if not result:
        return []

    allowed_categories = {
        "魚介",
        "煮干し",
        "鶏白湯",
        "豚骨",
        "醤油",
        "味噌",
        "塩",
        "辛い",
        "家系",
        "二郎系",
    }

    aliases = {
        "しょうゆ": "醤油",
        "しお": "塩",
    }

    categories = [
        aliases.get(c.strip(), c.strip())
        for c in result.split(",")
        if c.strip()
    ]
    return [c for c in categories if c in allowed_categories]


async def extract_ramen_category_mentions(
    editorial_summary: str | None,
    reviews: list[ReviewItem],
) -> dict[str, int]:
    sources: list[tuple[str, str]] = []

    if editorial_summary and editorial_summary.strip():
        sources.append(("editorial", editorial_summary.strip()))

    for idx, review in enumerate(reviews[:5], start=1):
        text = (review.get("text") or "").strip()
        if text:
            sources.append((f"review{idx}", text))

    if not sources:
        return {}

    prompt_lines = [
        "次の各ソースについて、ラーメンカテゴリを判定してください。",
        "候補: 魚介, 煮干し, 鶏白湯, 豚骨, 醤油, 味噌, 塩, 辛い, 家系, 二郎系",
        "出力形式は必ず各行を次の形で返すこと:",
        "source_id|カテゴリ1,カテゴリ2",
        "該当カテゴリが無い場合は source_id| だけ返すこと。",
        "",
    ]
    prompt_lines.extend(f"{source_id}: {text}" for source_id, text in sources)
    prompt = "\n".join(prompt_lines)

    resp = await client.responses.create(
        model="gpt-4o-mini",
        input=prompt,
    )

    output = (resp.output_text or "").strip()
    if not output:
        return {}

    allowed_categories = {
        "魚介",
        "煮干し",
        "鶏白湯",
        "豚骨",
        "醤油",
        "味噌",
        "塩",
        "辛い",
        "家系",
        "二郎系",
    }
    aliases = {
        "しょうゆ": "醤油",
        "しお": "塩",
    }
    valid_source_ids = {source_id for source_id, _ in sources}

    mentions: dict[str, int] = {}
    for line in output.splitlines():
        raw = line.strip()
        if not raw or "|" not in raw:
            continue
        source_id, categories_text = raw.split("|", 1)
        source_id = source_id.strip()
        if source_id not in valid_source_ids:
            continue

        categories = {
            aliases.get(c.strip(), c.strip())
            for c in categories_text.split(",")
            if c.strip()
        }

        for category in categories:
            if category in allowed_categories:
                mentions[category] = mentions.get(category, 0) + 1

    return mentions