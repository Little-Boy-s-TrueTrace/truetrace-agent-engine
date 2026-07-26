from cccd_validator import validate_format


def test_valid_vietnamese_cccd_format():
    result = validate_format("001200000001")
    assert result["valid"] is True
    assert result["province"] == "Hà Nội"
    assert result["birth_year"] == 2000


def test_rejects_unknown_province():
    assert validate_format("999200000001")["valid"] is False
