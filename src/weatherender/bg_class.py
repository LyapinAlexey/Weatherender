def determine_bg_class(condition_text: str) -> str:
    text = condition_text.lower()
    if any(word in text for word in ["clear", "sunny"]):
        return "sunny"
    if "rain" in text:
        return "rainy"
    if "cloud" in text:
        return "cloudy"
    if "thunder" in text:
        return "thunder"
    return "sunny"
