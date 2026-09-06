# backend/agents/nav_confirm.py
"""Second-turn handler: confirm_nav_yes_no.

The fault reply always ends with "Ready to set nav — yes or no?". The driver's
spoken answer arrives as a second ElevenLabs tool call (tool_name
confirm_nav_yes_no), which the graph routes to the nav_confirm branch — no
agents re-run, no cached fault reply is returned. This is the multi-turn gate
the audit's liability section asked for: dispatch-affecting nav action only
happens after an explicit driver "yes".
"""

_CONFIRM_KEYS = ("confirmed", "confirm", "answer", "yes_no", "response", "value")
_TRUTHY = {"yes", "y", "yeah", "yep", "true", "1", "confirm", "confirmed", "go", "ok", "okay", "set it", "do it"}
_FALSY = {"no", "n", "nope", "false", "0", "cancel", "stop", "not now"}


def parse_confirmation(parameters: dict) -> bool | None:
    """Normalize the ElevenLabs confirmation param -> True/False/None (ambiguous)."""
    for key in _CONFIRM_KEYS:
        if key not in parameters:
            continue
        val = parameters[key]
        if isinstance(val, bool):
            return val
        if isinstance(val, (int, float)):
            return bool(val)
        if isinstance(val, str):
            norm = val.strip().lower().rstrip(".,!?")
            if norm in _TRUTHY:
                return True
            if norm in _FALSY:
                return False
    # Fall back to scanning every string value for a bare yes/no.
    for val in parameters.values():
        if isinstance(val, str):
            norm = val.strip().lower().rstrip(".,!?")
            if norm in _TRUTHY:
                return True
            if norm in _FALSY:
                return False
    return None


def render_nav_reply(confirmed: bool | None, state: dict) -> str:
    shop = state.get("best_shop") or {}
    shop_name = state.get("destination") or shop.get("name") or "the shop"
    distance = shop.get("distance_miles")
    if confirmed is True:
        where = f"{shop_name}" + (f", {distance} miles ahead" if distance is not None else "")
        return (
            f"Navigation set — routing to {where}. "
            "Dispatch has your updated ETA. Drive safe, and say the word if you need anything else."
        )
    if confirmed is False:
        return (
            "No problem — holding your spot and leaving nav as is. "
            "Say the word if you want another shop or need dispatch updated."
        )
    return (
        "I didn't catch that — do you want me to set nav to the shop, yes or no?"
    )
