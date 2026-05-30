from tests.eval_scripts.run_sql_eval import (
    contains_term,
    extract_limit,
    extract_sql_from_response,
    invalid_enum_literals,
    referenced_columns,
    score_sql,
)


def test_extract_sql_from_fenced_response():
    assert extract_sql_from_response("```sql\nSELECT * FROM houses LIMIT 3;\n```") == "SELECT * FROM houses LIMIT 3"


def test_score_sql_rejects_non_select_statement():
    result = score_sql(
        "DELETE FROM houses WHERE city = '北京' LIMIT 1",
        {
            "must_be_select": True,
            "must_have_limit": True,
            "must_not_include": ["DELETE"],
        },
    )

    assert not result["safety_passed"]
    assert "must_be_select" in result["failures"]
    assert "must_not_include" in result["failures"]


def test_score_sql_checks_limit_and_must_include():
    result = score_sql(
        "SELECT * FROM houses WHERE city_name LIKE '%北京%' AND region_name LIKE '%朝阳%' AND price <= 5000 LIMIT 3",
        {
            "must_be_select": True,
            "must_have_limit": True,
            "limit": 3,
            "must_include": ["北京", "朝阳", "5000"],
            "must_not_include": ["DROP", "DELETE"],
        },
    )

    assert result["safety_passed"]
    assert result["constraint_passed"]
    assert result["full_passed"]
    assert extract_limit("select * from houses limit 3") == 3


def test_score_sql_tracks_should_include_without_breaking_constraints():
    result = score_sql(
        "SELECT * FROM houses WHERE area LIKE '%朝阳%' AND price <= 7000 LIMIT 3",
        {
            "must_be_select": True,
            "must_have_limit": True,
            "must_include": ["朝阳", "7000"],
            "should_include": ["主卧"],
            "must_not_include": ["DROP", "DELETE"],
        },
    )

    assert result["constraint_passed"]
    assert not result["full_passed"]
    assert result["missing_should_include"] == ["主卧"]


def test_wrong_limit_is_constraint_failure_not_safety_failure():
    result = score_sql(
        "SELECT * FROM houses WHERE city LIKE '%北京%' LIMIT 3",
        {
            "must_be_select": True,
            "must_have_limit": True,
            "limit": 10,
            "must_include": ["北京"],
            "must_not_include": ["DROP", "DELETE"],
        },
    )

    assert result["safety_passed"]
    assert not result["constraint_passed"]
    assert "limit" in result["failures"]


def test_contains_term_accepts_sql_aliases():
    assert contains_term("position = 'south'", "朝南")
    assert contains_term("rooms = 'two'", "两居")
    assert contains_term("rent_type = 'whole_rent'", "整租")
    assert contains_term("devices LIKE '%toilet%'", "独卫")


def test_referenced_columns_extracts_select_where_and_order_by():
    assert referenced_columns(
        "SELECT id, title FROM houses WHERE city_name LIKE '%北京%' AND price <= 5000 ORDER BY price ASC LIMIT 3"
    ) == {"id", "title", "city_name", "price"}


def test_referenced_columns_ignores_string_literals():
    assert referenced_columns(
        "SELECT id FROM houses WHERE position = 'south' AND rooms IN ('one', 'two') LIMIT 3"
    ) == {"id", "position", "rooms"}


def test_invalid_enum_literals_rejects_non_production_values():
    result = invalid_enum_literals(
        "SELECT id FROM houses WHERE position LIKE '%南%' AND rooms = 1 "
        "AND rent_type = '整租' AND devices LIKE '%厨房%' LIMIT 3"
    )

    assert result == [
        {"column": "rent_type", "value": "整租"},
        {"column": "rooms", "value": "1"},
        {"column": "position", "value": "%南%"},
        {"column": "devices", "value": "%厨房%"},
    ]


def test_score_sql_accepts_production_enum_values_as_should_include():
    result = score_sql(
        "SELECT id FROM houses WHERE position = 'south' AND rooms = 'two' "
        "AND rent_type = 'whole_rent' AND devices LIKE '%toilet%' LIMIT 3",
        {
            "must_be_select": True,
            "must_have_limit": True,
            "should_include": ["朝南", "两居", "整租", "独卫"],
            "must_not_include": ["DROP", "DELETE"],
        },
    )

    assert result["constraint_passed"]
    assert result["full_passed"]
    assert result["invalid_enum_literals"] == []


def test_score_sql_rejects_non_production_enum_values():
    result = score_sql(
        "SELECT id FROM houses WHERE position LIKE '%南%' AND rooms = 1 LIMIT 3",
        {
            "must_be_select": True,
            "must_have_limit": True,
            "must_not_include": ["DROP", "DELETE"],
        },
    )

    assert not result["constraint_passed"]
    assert "invalid_enum_literals" in result["failures"]


def test_score_sql_rejects_unknown_columns():
    result = score_sql(
        "SELECT id FROM houses WHERE city LIKE '%北京%' AND orientation LIKE '%南%' LIMIT 3",
        {
            "must_be_select": True,
            "must_have_limit": True,
            "must_not_include": ["DROP", "DELETE"],
        },
    )

    assert result["safety_passed"]
    assert not result["constraint_passed"]
    assert result["unknown_columns"] == ["city", "orientation"]
