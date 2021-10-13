import pytest
from night_rally import admin


@pytest.mark.parametrize(
    "test_input, expected",
    [
        ("20210928T200053Z", "20210928T000000Z"),
        ("20210928T000000Z", "20210928T000000Z"),
    ],
)
def test_at_midnight(test_input, expected):
    assert admin._at_midnight(test_input) == expected
