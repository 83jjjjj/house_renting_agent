import logging
import os
import re
import time
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pymysql

from tests.eval_scripts.common import (
    base_summary,
    build_parser,
    load_cases,
    make_report_dir,
    require_env,
    values_match,
    write_json,
    write_jsonl,
)
from tests.eval_scripts.run_sql_eval import (
    DEFAULT_CASE_FILE,
    generate_sql,
    normalize_sql,
    score_sql,
)

EVAL_NAME = "sql_exec"
DB_ENV_VARS = ["DB_USER", "DB_PASSWORD", "DB_HOST", "DB_PORT", "DB_NAME"]
EXECUTION_BLOCKLIST_PATTERNS = [
    r"\bfor\s+update\b",
    r"\block\s+in\s+share\s+mode\b",
    r"\binto\s+(?:out|dump)file\b",
    r"\bsleep\s*\(",
    r"\bbenchmark\s*\(",
    r"\bload_file\s*\(",
]
TEXT_PREDICATE_COLUMNS = {
    "title",
    "rent_type",
    "house_type",
    "rooms",
    "position",
    "intro",
    "devices",
    "city_name",
    "region_name",
    "community_name",
    "detail_address",
}
logger = logging.getLogger(__name__)

RESULT_VALUE_ALIASES = {
    "south": ["south", "朝南", "南"],
    "north": ["north", "朝北", "北"],
    "east": ["east", "朝东", "东"],
    "west": ["west", "朝西", "西"],
    "whole_rent": ["whole_rent", "整租", "不合租", "不要合租"],
    "one": ["one", "一居", "一居室", "1室", "1室1厅", "1室1厅1卫"],
    "two": ["two", "两居", "两居室", "2室", "2室1厅", "2室1厅1卫"],
    "three": ["three", "三居", "三居室", "3室", "3室1厅", "3室1厅1卫", "3室1厅2卫"],
    "toilet": ["toilet", "独卫", "卫生间", "卫"],
    "cook": ["cook", "厨房", "做饭", "可做饭"],
    "gas": ["gas", "厨房", "做饭", "可做饭"],
    "balcony": ["balcony", "阳台"],
    "icebox": ["icebox", "冰箱"],
    "washer": ["washer", "洗衣机"],
    "aircondition": ["aircondition", "空调"],
}


def normalize_column_name(column: str) -> str:
    return column.split(".")[-1].strip("`").lower()


def get_row_value(row: dict, column: str):
    normalized_column = normalize_column_name(column)
    for key, value in row.items():
        if normalize_column_name(str(key)) == normalized_column:
            return value
    return None


def json_safe_value(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def json_safe_row(row: dict) -> dict:
    return {str(key): json_safe_value(value) for key, value in row.items()}


def result_value_matches(expected: str, actual) -> bool:
    if values_match(expected, actual):
        return True

    actual_text = str(actual)
    actual_terms = {term.strip().lower() for term in re.split(r"[，,、;；\s]+", actual_text) if term.strip()}
    expected_text = str(expected).strip().lower()

    for canonical, aliases in RESULT_VALUE_ALIASES.items():
        normalized_aliases = {alias.lower() for alias in aliases}
        if expected_text in normalized_aliases and (
            canonical in actual_terms or any(alias in actual_text.lower() for alias in normalized_aliases)
        ):
            return True
        if expected_text == canonical and actual_terms & normalized_aliases:
            return True
    return False


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = (len(ordered) - 1) * q
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    weight = index - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def execution_safety_failures(sql: str) -> list[str]:
    normalized = normalize_sql(sql)
    failures = []
    if ";" in normalized:
        failures.append("multiple_statements")
    for pattern in EXECUTION_BLOCKLIST_PATTERNS:
        if re.search(pattern, normalized, flags=re.IGNORECASE):
            failures.append(pattern)
    return failures


def to_decimal(value) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def extract_price_bounds(sql: str) -> dict:
    normalized = normalize_sql(sql).replace("`", "")
    price_ref = r"(?:[a-zA-Z_][a-zA-Z0-9_]*\.)?price"
    min_price: Decimal | None = None
    max_price: Decimal | None = None

    for match in re.finditer(
        rf"\b{price_ref}\s+between\s+([0-9]+(?:\.[0-9]+)?)\s+and\s+([0-9]+(?:\.[0-9]+)?)\b",
        normalized,
        flags=re.IGNORECASE,
    ):
        low = Decimal(match.group(1))
        high = Decimal(match.group(2))
        min_price = low if min_price is None else max(min_price, low)
        max_price = high if max_price is None else min(max_price, high)

    for match in re.finditer(
        rf"\b{price_ref}\s*(<=|<|=|>=|>)\s*([0-9]+(?:\.[0-9]+)?)",
        normalized,
        flags=re.IGNORECASE,
    ):
        operator = match.group(1)
        value = Decimal(match.group(2))
        if operator in {"<=", "<"}:
            max_price = value if max_price is None else min(max_price, value)
        elif operator in {">=", ">"}:
            min_price = value if min_price is None else max(min_price, value)
        else:
            min_price = value if min_price is None else max(min_price, value)
            max_price = value if max_price is None else min(max_price, value)

    return {
        "min_price": float(min_price) if min_price is not None else None,
        "max_price": float(max_price) if max_price is not None else None,
    }


def extract_where_clause(sql: str) -> str:
    match = re.search(
        r"\bwhere\b(.*?)(?:\border\s+by\b|\blimit\b|$)",
        normalize_sql(sql),
        flags=re.IGNORECASE,
    )
    return match.group(1) if match else ""


def extract_text_constraints(sql: str) -> tuple[list[dict], list[dict]]:
    where_clause = extract_where_clause(sql)
    identifier = r"(?:`?[a-zA-Z_][a-zA-Z0-9_]*`?\.)?`?[a-zA-Z_][a-zA-Z0-9_]*`?"
    constraints = []
    for match in re.finditer(
        rf"({identifier})\s+(=|like)\s+(['\"])(.*?)\3",
        where_clause,
        flags=re.IGNORECASE,
    ):
        column = normalize_column_name(match.group(1))
        term = match.group(4).strip("%")
        if column in TEXT_PREDICATE_COLUMNS and term:
            constraints.append({"column": column, "term": term})

    if re.search(r"\bor\b", where_clause, flags=re.IGNORECASE):
        return [], constraints
    return constraints, []


def check_result_constraints(rows: list[dict], sql: str) -> dict:
    failures = []
    unchecked_constraints = []
    actual_limit = re.search(r"\blimit\s+(\d+)\b", normalize_sql(sql), flags=re.IGNORECASE)
    limit = int(actual_limit.group(1)) if actual_limit else None
    price_bounds = extract_price_bounds(sql)
    text_constraints, skipped_text_constraints = extract_text_constraints(sql)

    if limit is not None and len(rows) > limit:
        failures.append("row_limit")

    if rows:
        min_price = to_decimal(price_bounds["min_price"])
        max_price = to_decimal(price_bounds["max_price"])
        if min_price is not None or max_price is not None:
            for row in rows:
                price = to_decimal(get_row_value(row, "price"))
                if price is None:
                    unchecked_constraints.append({"type": "price", "reason": "price_not_selected"})
                    break
                if min_price is not None and price < min_price:
                    failures.append("price_min")
                    break
                if max_price is not None and price > max_price:
                    failures.append("price_max")
                    break

        for constraint in text_constraints:
            column = constraint["column"]
            term = constraint["term"]
            for row in rows:
                value = get_row_value(row, column)
                if value is None:
                    unchecked_constraints.append(
                        {"type": "like", "column": column, "term": term, "reason": "column_not_selected"}
                    )
                    break
                if not result_value_matches(term, value):
                    failures.append(f"like:{column}")
                    break

    unchecked_constraints.extend(
        {"type": "like", **constraint, "reason": "or_predicate_skipped"}
        for constraint in skipped_text_constraints
    )

    return {
        "row_count": len(rows),
        "non_empty": bool(rows),
        "limit": limit,
        "price_bounds": price_bounds,
        "text_constraints": text_constraints,
        "unchecked_constraints": unchecked_constraints,
        "failures": sorted(set(failures)),
        "result_constraints_passed": bool(rows) and not failures,
    }


def case_passed(static_scores: dict, execution: dict, result_checks: dict) -> bool:
    return (
        static_scores["constraint_passed"]
        and execution["passed"]
        and result_checks["result_constraints_passed"]
    )


def connect_database(connect_timeout: int, read_timeout: int):
    return pymysql.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
        connect_timeout=connect_timeout,
        read_timeout=read_timeout,
        write_timeout=read_timeout,
    )


def execute_sql(connection, sql: str, max_preview_rows: int) -> dict:
    started_at = time.perf_counter()
    with connection.cursor() as cursor:
        cursor.execute(sql)
        rows = cursor.fetchall()
    latency_ms = (time.perf_counter() - started_at) * 1000
    safe_rows = [json_safe_row(row) for row in rows]
    return {
        "passed": True,
        "latency_ms": latency_ms,
        "row_count": len(safe_rows),
        "preview_rows": safe_rows[:max_preview_rows],
        "all_rows_for_checks": safe_rows,
        "error": None,
    }


def run_eval(
    case_file: Path,
    output: Path | None,
    max_cases: int | None,
    connect_timeout: int,
    read_timeout: int,
    max_preview_rows: int,
):
    require_env("DEEPSEEK_API_KEY")
    for env_var in DB_ENV_VARS:
        require_env(env_var)

    cases = load_cases(case_file, max_cases=max_cases)
    report_dir = make_report_dir(EVAL_NAME, output)

    rows = []
    failures = []
    connection = connect_database(connect_timeout, read_timeout)

    try:
        for case in cases:
            try:
                sql, preferences = generate_sql(case["input"])
                generation_error = None
            except Exception as exc:
                sql = ""
                preferences = {}
                generation_error = repr(exc)

            scores = (
                score_sql(sql, case["expected_constraints"])
                if sql
                else {
                    "must_be_select": False,
                    "has_limit": False,
                    "expected_limit": case["expected_constraints"].get("limit"),
                    "actual_limit": None,
                    "missing_must_include": case["expected_constraints"].get("must_include", []),
                    "missing_should_include": case["expected_constraints"].get("should_include", []),
                    "found_forbidden": [],
                    "invalid_enum_literals": [],
                    "failures": ["error"],
                    "safety_passed": False,
                    "constraint_passed": False,
                    "full_passed": False,
                }
            )

            execution = {
                "attempted": False,
                "passed": False,
                "latency_ms": None,
                "row_count": 0,
                "preview_rows": [],
                "error": generation_error,
            }
            result_checks = {
                "row_count": 0,
                "non_empty": False,
                "limit": scores.get("actual_limit"),
                "price_bounds": {"min_price": None, "max_price": None},
                "text_constraints": [],
                "unchecked_constraints": [],
                "failures": ["not_executed"],
                "result_constraints_passed": False,
            }

            if sql and scores["safety_passed"]:
                execution["attempted"] = True
                exec_safety_failures = execution_safety_failures(sql)
                if exec_safety_failures:
                    execution["passed"] = False
                    execution["error"] = f"execution_safety_failures: {exec_safety_failures}"
                    result_checks["failures"] = ["execution_safety"]
                else:
                    try:
                        execution = {"attempted": True, **execute_sql(connection, sql, max_preview_rows)}
                        all_rows = execution.pop("all_rows_for_checks")
                        result_checks = check_result_constraints(all_rows, sql)
                    except Exception as exc:
                        execution["error"] = repr(exc)
                        result_checks["failures"] = ["db_error"]

            row = {
                "id": case["id"],
                "input": case["input"],
                "expected_constraints": case["expected_constraints"],
                "preferences": preferences,
                "sql": sql,
                "static_scores": scores,
                "execution": execution,
                "result_checks": result_checks,
                "passed": case_passed(scores, execution, result_checks),
                "tags": case.get("tags", []),
                "difficulty": case.get("difficulty"),
            }
            rows.append(row)
            if not row["passed"]:
                failures.append(row)
    finally:
        connection.close()

    total = len(rows)
    safety_passed = sum(row["static_scores"]["safety_passed"] for row in rows)
    constraint_passed = sum(row["static_scores"]["constraint_passed"] for row in rows)
    full_passed = sum(row["static_scores"]["full_passed"] for row in rows)
    exec_attempted = sum(row["execution"]["attempted"] for row in rows)
    exec_passed = sum(row["execution"]["passed"] for row in rows)
    non_empty = sum(row["result_checks"]["non_empty"] for row in rows)
    result_constraints_passed = sum(
        row["result_checks"]["result_constraints_passed"] for row in rows
    )
    unchecked_result_constraint_cases = sum(
        bool(row["result_checks"]["unchecked_constraints"]) for row in rows
    )
    latencies = [
        row["execution"]["latency_ms"]
        for row in rows
        if isinstance(row["execution"]["latency_ms"], int | float)
    ]

    summary = base_summary(EVAL_NAME, case_file, total)
    summary.update(
        {
            "safety_passed": safety_passed,
            "safety_rate": safety_passed / total if total else 0.0,
            "constraint_passed": constraint_passed,
            "constraint_rate": constraint_passed / total if total else 0.0,
            "full_passed": full_passed,
            "full_pass_rate": full_passed / total if total else 0.0,
            "exec_attempted": exec_attempted,
            "exec_attempt_rate": exec_attempted / total if total else 0.0,
            "exec_passed": exec_passed,
            "exec_rate": exec_passed / exec_attempted if exec_attempted else 0.0,
            "exec_success_rate": exec_passed / total if total else 0.0,
            "db_error_rate": (exec_attempted - exec_passed) / exec_attempted
            if exec_attempted
            else 0.0,
            "non_empty_results": non_empty,
            "non_empty_rate": non_empty / exec_passed if exec_passed else 0.0,
            "empty_result_rate": (exec_passed - non_empty) / exec_passed if exec_passed else 0.0,
            "result_constraints_passed": result_constraints_passed,
            "result_constraint_rate": result_constraints_passed / exec_passed
            if exec_passed
            else 0.0,
            "unchecked_result_constraint_cases": unchecked_result_constraint_cases,
            "latency_avg_ms": sum(latencies) / len(latencies) if latencies else None,
            "latency_p95_ms": percentile(latencies, 0.95),
            "latency_p99_ms": percentile(latencies, 0.99),
        }
    )

    write_json(report_dir / "summary.json", summary)
    write_jsonl(report_dir / "cases.jsonl", rows)
    write_jsonl(report_dir / "failures.jsonl", failures)

    logger.info(
        "sql exec eval: safety %s/%s, exec %s/%s attempted, non-empty %s/%s",
        safety_passed,
        total,
        exec_passed,
        exec_attempted,
        non_empty,
        exec_passed,
    )
    logger.info(
        "exec_rate: %.4f, empty_result_rate: %.4f, result_constraint_rate: %.4f",
        summary["exec_rate"],
        summary["empty_result_rate"],
        summary["result_constraint_rate"],
    )
    logger.info("report: %s", report_dir)


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = build_parser("评估 SQL 静态安全与真实 MySQL 可执行性。", DEFAULT_CASE_FILE)
    parser.add_argument("--connect-timeout", type=int, default=5, help="MySQL 连接超时秒数。")
    parser.add_argument("--read-timeout", type=int, default=15, help="MySQL 读写超时秒数。")
    parser.add_argument(
        "--max-preview-rows",
        type=int,
        default=3,
        help="每条样本最多写入报告的结果预览行数。",
    )
    args = parser.parse_args()
    run_eval(
        args.case_file,
        args.output,
        args.max_cases,
        args.connect_timeout,
        args.read_timeout,
        args.max_preview_rows,
    )


if __name__ == "__main__":
    main()
