from benneria.hebrew import consonantal, pointed


def test_pointed_keeps_vowels_and_drops_cantillation():
    assert pointed("בָּרָ֣א") == "בָּרָא"
    assert pointed("הָ/אָֽרֶץ") == "הָאָרֶץ"  # meteg and the morpheme separator removed


def test_consonantal_drops_all_points():
    assert consonantal("וַיִּשְׁמְרוּ") == "וישמרו"
    assert consonantal("שָׂדֶה") == "שדה"  # sin dot removed


def test_normalization_is_nfc():
    # Same word, combining marks in a different order.
    assert pointed("בָּ") == pointed("בָּ")


def test_empty_input():
    assert pointed(None) == "" and consonantal("") == ""
