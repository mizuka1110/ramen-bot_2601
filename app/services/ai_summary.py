from openai import OpenAI

client = OpenAI()  # OPENAI_API_KEY を環境変数から読む

async def summarize_reviews_30(reviews: list[dict]) -> str | None:
    texts = [
        r["text"].strip()
        for r in reviews
        if (r.get("rating") or 0) >= 4 and r.get("text")
    ][:5]

    if not texts:
        return None

    prompt = (
        "次の口コミを日本語で30字程度に要約して。"
        "出力は1文のみで、客観的な文体にする。\n\n"
        + "\n".join(f"- {t}" for t in texts)
    )

    resp = client.responses.create(
        model="gpt-4o-mini",
        input=prompt,
    )

    summary = (resp.output_text or "").strip()
    return summary or None
