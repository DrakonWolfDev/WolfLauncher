def browser_style_terms(style: str) -> list[str]:
    if style == "PvE":
        return ["pve", "p.v.e", "no pvp", "no kos", "no-kos", "no kill on sight"]
    if style == "PvP":
        return ["pvp", "p.v.p"]
    return []


def players_text(current: int | None, maximum: int | None) -> str:
    if current is None and maximum is None:
        return ""
    if maximum is None:
        return str(current)
    if current is None:
        return f"?/{maximum}"
    return f"{current}/{maximum}"


def browser_summary_text(summary: dict[str, int], shown: int, match_count: int, limit: int) -> str:
    total = summary["total"]
    if total == 0:
        return "Cached discovered servers: empty"

    parts = [
        f"Showing {shown} of {match_count} matching",
        f"{total} cached",
        f"{summary['online']} online",
        f"{summary['checked']} checked",
        f"{summary['seen']} seen online",
    ]
    if shown == limit and match_count > shown:
        parts[0] = f"Showing first {shown} of {match_count} matching"
    elif shown == 0:
        parts[0] = f"No matches from {total} cached"
    return "Cached discovered servers: " + " | ".join(parts)
