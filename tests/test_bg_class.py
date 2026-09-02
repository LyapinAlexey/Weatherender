from weatherender.bg_class import determine_bg_class


class TestBgClass:
    def test_bg_class_sunny_from_clear(self):
        assert determine_bg_class("clear sky") == "sunny"

    def test_bg_class_sunny_from_sunny_word(self):
        assert determine_bg_class("sunny") == "sunny"

    def test_bg_class_rainy(self):
        assert determine_bg_class("light rain") == "rainy"

    def test_bg_class_cloudy(self):
        assert determine_bg_class("overcast clouds") == "cloudy"

    def test_bg_class_thunder(self):
        assert determine_bg_class("thunderstorm") == "thunder"

    def test_bg_class_default_unknown_condition(self):
        assert determine_bg_class("fog") == "sunny"

    def test_bg_class_case_insensitive(self):
        assert determine_bg_class("SUNNY") == "sunny"

    def test_bg_class_priority_when_multiple_keywords_present(self):
        assert determine_bg_class("cloudy with rain") == "rainy"
