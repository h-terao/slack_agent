from .utils import register


@register
def get_current_weather(city: str) -> dict[str, str]:
    """Get current weather at the specified city.

    Args:
        city: City name.

    Returns:
        dict: Weather information.
    """
    return {"city": city, "weather": "sunny", "temperature": 30, "unit": "C"}
