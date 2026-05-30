from tests.eval_scripts.common import is_empty_value, values_match
from tests.eval_scripts.run_slot_eval import score_case


def test_values_match_accepts_reordered_comma_terms():
    assert values_match("不要朝北，阳台", "最好有阳台，不要朝北")


def test_values_match_keeps_alternative_area_strict():
    assert not values_match("朝阳或海淀", "朝阳")


def test_score_case_ignores_none_like_actual_values():
    result = score_case(
        {"budget_max": 7000, "area": "朝阳或海淀", "others": "朝向无所谓"},
        {"budget_max": 7000.0, "area": "朝阳", "orientation": "None"},
    )

    assert result["false_positive_fields"] == []
    assert result["wrong_fields"] == ["area"]
    assert result["false_negative_fields"] == ["area", "others"]


def test_empty_value_detection():
    assert is_empty_value("None")
    assert is_empty_value("无所谓")
    assert not is_empty_value("朝向无所谓")
