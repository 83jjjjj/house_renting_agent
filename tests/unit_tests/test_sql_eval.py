from tests.eval_scripts.run_sql_eval import (
    contains_term,
    extract_limit,
    extract_sql_from_response,
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
        "SELECT * FROM houses WHERE city LIKE '%北京%' AND area LIKE '%朝阳%' AND price <= 5000 LIMIT 3",
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
    assert contains_term("orientation LIKE '%南%'", "朝南")
    assert contains_term("house_type LIKE '%两室一厅%'", "两居")
