import pytest

from benneria.refs import RefError, in_ref, to_osis


@pytest.mark.parametrize("ref, osis", [
    ("Leviticus 19.3", "Lev.19.3"),
    ("Lev 19:3", "Lev.19.3"),
    ("Gen.1.1", "Gen.1.1"),
    ("I Samuel 3:4", "1Sam.3.4"),
    ("1Sam.3.4", "1Sam.3.4"),
    ("2 Kings 5", "2Kgs.5"),
    ("Psalm 23", "Ps.23"),
    ("Song of Songs 2:1", "Song.2.1"),
    ("Ruth", "Ruth"),
    ("Eccles 1:2", "Eccl.1.2"),
    ("Isaiah 40:1-5", "Isa.40.1"),
    ("genesis_1_1", "Gen.1.1"),
])
def test_to_osis(ref, osis):
    assert to_osis(ref) == osis


@pytest.mark.parametrize("ref, message", [
    ("Jo 1:1", "Ambiguous book"),
    ("Matthew 1:1", "Unknown book"),
    ("", "Not a Bible reference"),
])
def test_to_osis_errors(ref, message):
    with pytest.raises(RefError, match=message):
        to_osis(ref)


def test_in_ref():
    assert in_ref("Gen.1.1", "Gen.1.1")
    assert in_ref("Gen.1.1", "Gen.1")
    assert in_ref("Gen.1.1", "Gen")
    assert not in_ref("Gen.1.10", "Gen.1.1")
    assert not in_ref("Gen.11.1", "Gen.1")
