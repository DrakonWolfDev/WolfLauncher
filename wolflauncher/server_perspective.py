"""Interpret advertised DayZ perspective without guessing from server names."""


def perspective_from_keywords(value: object) -> str:
    if isinstance(value, str):
        tags = {tag.strip().casefold() for tag in value.split(",") if tag.strip()}
    elif isinstance(value, list) and all(isinstance(tag, str) for tag in value):
        tags = {tag.strip().casefold() for tag in value if tag.strip()}
    else:
        return "unknown"
    if "no3rd" in tags:
        return "first_person"
    # A classification such as "mod" alone is not a complete query response.
    if tags & {"battleye", "external", "privhive"} or any(
        tag.startswith("etm") or (len(tag) == 5 and tag[2] == ":") for tag in tags
    ):
        return "third_person"
    return "unknown"


def perspective_label(value: str) -> str:
    return {
        "first_person": "First-person only",
        "third_person": "Third-person enabled",
    }.get(value, "Unknown")
