def sort_items(items: list[dict]) -> list[dict]:
    return sorted(
        items,
        key=lambda x: (
            not (x.get("open_now") is True),
            -(x.get("rating") or 0),
            -(x.get("rating_count") or 0),
        )
    )
