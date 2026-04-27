"""Backward-compatible shim — delegates to canton registry."""

from nupla.cantons import get_canton


async def get_gemeinden(force_refresh: bool = False) -> list[dict[str, str]]:
    """Get Zurich Gemeinden. Delegates to canton registry."""
    result = await get_canton("zh", force_refresh=force_refresh)
    return result or []
