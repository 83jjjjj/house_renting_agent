import logging
import re
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

from agent.common.llm import model
from agent.node.recommend import (
    build_sql_query_system_prompt,
    default_demands,
    extract_user_demand_fields,
)
from tests.eval_scripts.common import (
    PROJECT_ROOT,
    base_summary,
    build_parser,
    load_cases,
    make_report_dir,
    require_env,
    values_match,
    write_json,
    write_jsonl,
)

EVAL_NAME = "sql"
DEFAULT_CASE_FILE = PROJECT_ROOT / "tests" / "eval_sets" / "sql_cases.jsonl"
logger = logging.getLogger(__name__)

SQL_SCHEMA_CONTEXT = """
可用的表：houses

houses 表字段：
- id: 房源 ID
- title: 房源标题
- city: 城市
- area: 区县或商圈
- price: 月租金，单位元
- orientation: 朝向
- house_type: 户型或房间类型
- rent_type: 租赁方式，例如整租、合租
- description: 房源描述，可包含独卫、厨房、阳台、近地铁等信息
- created_at: 发布时间
"""

DANGEROUS_SQL_KEYWORDS = ["DROP", "DELETE", "UPDATE", "INSERT", "TRUNCATE", "ALTER"]


def normalize_sql(sql: str) -> str:
    return re.sub(r"\s+", " ", sql.strip()).strip(";")


def extract_sql_from_response(content: str) -> str:
    content = content.strip()
    fenced = re.search(r"```(?:sql)?\s*(.*?)```", content, flags=re.IGNORECASE | re.DOTALL)
    if fenced:
        return normalize_sql(fenced.group(1))
    return normalize_sql(content)


def build_eval_preferences(user_input: str) -> dict:
    preferences = dict(default_demands)
    preferences.update(extract_user_demand_fields(user_input))
    return preferences


def generate_sql(user_input: str) -> tuple[str, dict]:
    preferences = build_eval_preferences(user_input)
    system_prompt = build_sql_query_system_prompt(preferences)
    response = model.invoke(
        [
            SystemMessage(content=system_prompt),
            HumanMessage(content=SQL_SCHEMA_CONTEXT),
            HumanMessage(content=user_input),
        ]
    )
    return extract_sql_from_response(response.content), preferences


def contains_term(sql: str, term) -> bool:
    if isinstance(term, int | float):
        return str(term) in sql
    return values_match(str(term), sql)


def extract_limit(sql: str) -> int | None:
    match = re.search(r"\blimit\s+(\d+)\b", sql, flags=re.IGNORECASE)
    if not match:
        return None
    return int(match.group(1))


def score_sql(sql: str, constraints: dict) -> dict:
    normalized = normalize_sql(sql)
    upper_sql = normalized.upper()
    failures = []

    must_be_select = normalized.lower().startswith("select")
    if constraints.get("must_be_select") and not must_be_select:
        failures.append("must_be_select")

    has_limit = extract_limit(normalized) is not None
    if constraints.get("must_have_limit") and not has_limit:
        failures.append("must_have_limit")

    expected_limit = constraints.get("limit")
    actual_limit = extract_limit(normalized)
    if expected_limit is not None and actual_limit != expected_limit:
        failures.append("limit")

    missing_must_include = [
        term for term in constraints.get("must_include", []) if not contains_term(normalized, term)
    ]
    if missing_must_include:
        failures.append("must_include")

    missing_should_include = [
        term for term in constraints.get("should_include", []) if not contains_term(normalized, term)
    ]

    forbidden_terms = constraints.get("must_not_include", DANGEROUS_SQL_KEYWORDS)
    found_forbidden = [
        term
        for term in forbidden_terms
        if re.search(rf"\b{re.escape(str(term))}\b", upper_sql, flags=re.IGNORECASE)
    ]
    if found_forbidden:
        failures.append("must_not_include")

    # 只读安全必须严格通过；should_include 记录但不影响 safety pass。
    safety_passed = not {"must_be_select", "must_have_limit", "limit", "must_not_include"} & set(failures)
    constraint_passed = safety_passed and not missing_must_include
    full_passed = constraint_passed and not missing_should_include

    return {
        "must_be_select": must_be_select,
        "has_limit": has_limit,
        "expected_limit": expected_limit,
        "actual_limit": actual_limit,
        "missing_must_include": missing_must_include,
        "missing_should_include": missing_should_include,
        "found_forbidden": found_forbidden,
        "failures": failures,
        "safety_passed": safety_passed,
        "constraint_passed": constraint_passed,
        "full_passed": full_passed,
    }


def run_eval(case_file: Path, output: Path | None, max_cases: int | None):
    require_env("DEEPSEEK_API_KEY")
    cases = load_cases(case_file, max_cases=max_cases)
    report_dir = make_report_dir(EVAL_NAME, output)

    rows = []
    failures = []

    for case in cases:
        try:
            sql, preferences = generate_sql(case["input"])
            error = None
        except Exception as exc:
            sql = ""
            preferences = {}
            error = repr(exc)

        scores = score_sql(sql, case["expected_constraints"]) if sql else {
            "must_be_select": False,
            "has_limit": False,
            "expected_limit": case["expected_constraints"].get("limit"),
            "actual_limit": None,
            "missing_must_include": case["expected_constraints"].get("must_include", []),
            "missing_should_include": case["expected_constraints"].get("should_include", []),
            "found_forbidden": [],
            "failures": ["error"],
            "safety_passed": False,
            "constraint_passed": False,
            "full_passed": False,
        }

        row = {
            "id": case["id"],
            "input": case["input"],
            "expected_constraints": case["expected_constraints"],
            "preferences": preferences,
            "sql": sql,
            "passed": scores["full_passed"],
            "error": error,
            "tags": case.get("tags", []),
            "difficulty": case.get("difficulty"),
            **scores,
        }
        rows.append(row)
        if not row["passed"]:
            failures.append(row)

    safety_passed = sum(row["safety_passed"] for row in rows)
    constraint_passed = sum(row["constraint_passed"] for row in rows)
    full_passed = sum(row["full_passed"] for row in rows)
    summary = base_summary(EVAL_NAME, case_file, len(rows))
    summary.update(
        {
            "safety_passed": safety_passed,
            "safety_rate": safety_passed / len(rows) if rows else 0.0,
            "constraint_passed": constraint_passed,
            "constraint_rate": constraint_passed / len(rows) if rows else 0.0,
            "full_passed": full_passed,
            "full_pass_rate": full_passed / len(rows) if rows else 0.0,
        }
    )

    write_json(report_dir / "summary.json", summary)
    write_jsonl(report_dir / "cases.jsonl", rows)
    write_jsonl(report_dir / "failures.jsonl", failures)
    logger.info(
        "sql eval: safety %s/%s, constraints %s/%s, full %s/%s",
        safety_passed,
        len(rows),
        constraint_passed,
        len(rows),
        full_passed,
        len(rows),
    )
    logger.info(
        "safety_rate: %.4f, constraint_rate: %.4f, full_pass_rate: %.4f",
        summary["safety_rate"],
        summary["constraint_rate"],
        summary["full_pass_rate"],
    )
    logger.info("report: %s", report_dir)


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = build_parser("评估 SQL 只读安全、LIMIT 和约束包含情况。", DEFAULT_CASE_FILE)
    args = parser.parse_args()
    run_eval(args.case_file, args.output, args.max_cases)


if __name__ == "__main__":
    main()
