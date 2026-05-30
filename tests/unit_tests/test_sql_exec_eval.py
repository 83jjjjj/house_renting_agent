from decimal import Decimal

from tests.eval_scripts.run_sql_exec_eval import (
    case_passed,
    check_result_constraints,
    execution_safety_failures,
    extract_price_bounds,
    extract_text_constraints,
    json_safe_row,
    percentile,
    result_value_matches,
)


def test_extract_price_bounds_from_between_and_comparisons():
    assert extract_price_bounds(
        "SELECT * FROM houses WHERE price BETWEEN 3000 AND 8000 AND price <= 7000 LIMIT 3"
    ) == {"min_price": 3000.0, "max_price": 7000.0}


def test_extract_text_constraints_skips_or_predicates():
    checked, skipped = extract_text_constraints(
        "SELECT * FROM houses WHERE region_name LIKE '%朝阳%' OR region_name LIKE '%海淀%' LIMIT 10"
    )

    assert checked == []
    assert skipped == [
        {"column": "region_name", "term": "朝阳"},
        {"column": "region_name", "term": "海淀"},
    ]


def test_check_result_constraints_passes_matching_rows():
    sql = (
        "SELECT id, price, city_name, region_name FROM houses "
        "WHERE city_name LIKE '%北京%' AND region_name = '朝阳' "
        "AND price >= 3000 AND price <= 8000 LIMIT 2"
    )
    rows = [
        {"id": 1, "price": Decimal("5000.00"), "city_name": "北京", "region_name": "朝阳"},
        {"id": 2, "price": Decimal("7800.00"), "city_name": "北京市", "region_name": "朝阳区"},
    ]

    result = check_result_constraints(rows, sql)

    assert result["result_constraints_passed"]
    assert result["row_count"] == 2
    assert result["failures"] == []


def test_sql_exec_case_requires_static_constraints():
    assert not case_passed(
        {"safety_passed": True, "constraint_passed": False},
        {"passed": True},
        {"result_constraints_passed": True},
    )

    assert case_passed(
        {"safety_passed": True, "constraint_passed": True},
        {"passed": True},
        {"result_constraints_passed": True},
    )


def test_check_result_constraints_accepts_production_enum_values():
    sql = (
        "SELECT id, price, position, rooms, rent_type, devices FROM houses "
        "WHERE position = 'south' AND rooms = 'one' AND rent_type = 'whole_rent' "
        "AND devices LIKE '%toilet%' AND price <= 8000 LIMIT 2"
    )
    rows = [
        {
            "id": 1,
            "price": Decimal("6500.00"),
            "position": "south",
            "rooms": "one",
            "rent_type": "whole_rent",
            "devices": "toilet,cook,gas,aircondition",
        }
    ]

    result = check_result_constraints(rows, sql)

    assert result["result_constraints_passed"]
    assert result["failures"] == []


def test_result_value_matches_chinese_terms_to_production_values():
    assert result_value_matches("朝南", "south")
    assert result_value_matches("一居", "one")
    assert result_value_matches("整租", "whole_rent")
    assert result_value_matches("独卫", "toilet,cook,gas")


def test_check_result_constraints_fails_price_and_text_mismatch():
    sql = (
        "SELECT id, price, city_name FROM houses "
        "WHERE city_name LIKE '%北京%' AND price <= 8000 LIMIT 3"
    )
    rows = [{"id": 1, "price": Decimal("9000.00"), "city_name": "上海"}]

    result = check_result_constraints(rows, sql)

    assert not result["result_constraints_passed"]
    assert "price_max" in result["failures"]
    assert "like:city_name" in result["failures"]


def test_check_result_constraints_treats_empty_result_as_not_passed():
    result = check_result_constraints(
        [],
        "SELECT id FROM houses WHERE city_name LIKE '%北京%' LIMIT 3",
    )

    assert not result["result_constraints_passed"]
    assert result["non_empty"] is False


def test_check_result_constraints_records_unchecked_missing_selected_column():
    result = check_result_constraints(
        [{"id": 1, "title": "北京朝阳房源"}],
        "SELECT id, title FROM houses WHERE city_name LIKE '%北京%' LIMIT 3",
    )

    assert result["result_constraints_passed"]
    assert result["unchecked_constraints"] == [
        {
            "type": "like",
            "column": "city_name",
            "term": "北京",
            "reason": "column_not_selected",
        }
    ]


def test_percentile_interpolates_values():
    assert percentile([10, 20, 30, 40], 0.95) == 38.5
    assert percentile([], 0.95) is None


def test_execution_safety_failures_rejects_multi_statement_and_locking_select():
    failures = execution_safety_failures(
        "SELECT * FROM houses LIMIT 3; SELECT SLEEP(1) FOR UPDATE"
    )

    assert "multiple_statements" in failures
    assert any("sleep" in failure for failure in failures)
    assert any("for" in failure for failure in failures)


def test_json_safe_row_serializes_decimal_and_bytes():
    assert json_safe_row({"price": Decimal("123.45"), "raw": b"\xe5\x8c\x97\xe4\xba\xac"}) == {
        "price": 123.45,
        "raw": "北京",
    }
