from homekeeper.domain import matching


def test_match_returns_repairman_with_overlapping_word():
    repairmen = [{"name": "A", "phone": "0901", "service_type": "điều hòa lạnh"}]
    result = matching.match_repairmen("điều hòa phòng ngủ không mát", repairmen)
    assert len(result) == 1


def test_match_case_insensitive():
    repairmen = [{"name": "B", "phone": "0902", "service_type": "Điện Lạnh"}]
    result = matching.match_repairmen("điện lạnh bị hỏng", repairmen)
    assert len(result) == 1


def test_no_match_returns_empty():
    repairmen = [{"name": "C", "phone": "0903", "service_type": "ống nước"}]
    result = matching.match_repairmen("điều hòa hỏng", repairmen)
    assert result == []


def test_empty_repairmen_returns_empty():
    result = matching.match_repairmen("bất kỳ mô tả", [])
    assert result == []


def test_multiple_repairmen_filtered():
    repairmen = [
        {"name": "A", "phone": "0901", "service_type": "điều hòa"},
        {"name": "B", "phone": "0902", "service_type": "ống nước"},
    ]
    result = matching.match_repairmen("điều hòa bị hỏng", repairmen)
    assert len(result) == 1
    assert result[0]["name"] == "A"


def test_multiple_matches_all_returned():
    repairmen = [
        {"name": "A", "phone": "0901", "service_type": "điều hòa"},
        {"name": "B", "phone": "0902", "service_type": "điều hòa điện"},
    ]
    result = matching.match_repairmen("điều hòa hỏng", repairmen)
    assert len(result) == 2


def test_returns_original_repairman_objects():
    r = {"name": "X", "phone": "0999", "service_type": "điện"}
    result = matching.match_repairmen("điện hỏng", [r])
    assert result[0] is r


def test_punctuation_in_description_does_not_block_match():
    repairmen = [{"name": "A", "phone": "0901", "service_type": "điều hòa"}]
    result = matching.match_repairmen("điều hòa hỏng.", repairmen)
    assert len(result) == 1


def test_punctuation_in_service_type_does_not_block_match():
    repairmen = [{"name": "B", "phone": "0902", "service_type": "điều hòa."}]
    result = matching.match_repairmen("điều hòa bị hỏng", repairmen)
    assert len(result) == 1


def test_comma_in_description_does_not_block_match():
    repairmen = [{"name": "C", "phone": "0903", "service_type": "điện lạnh"}]
    result = matching.match_repairmen("máy lạnh, bị rò điện", repairmen)
    assert len(result) == 1
