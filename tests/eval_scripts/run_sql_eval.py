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
- id: 主键id
- user_id: 房东id
- title: 标题
- rent_type: 租房类型，生产值为英文枚举，例如 whole_rent 表示整租，worry_free_rental 表示省心租
- floor: 所在楼层
- all_floor: 总楼层
- house_type: 户型
- rooms: 居室，生产值为英文枚举，例如 one、two、three
- position: 朝向，生产值为英文枚举，例如 south、north、east、west
- area: 面积，单位平方米
- price: 价格，单位元
- intro: 房屋介绍，可包含独卫、厨房、阳台、近地铁等信息
- devices: 设备，生产值为英文设备码，例如 toilet、cook、gas、balcony、icebox、washer、aircondition
- head_image: 头图
- images: 房源图
- city_id: 城市id
- city_name: 城市名
- region_id: 区域id
- region_name: 区域名
- community_name: 社区名
- detail_address: 详细地址
- longitude: 经度
- latitude: 纬度

常见语义映射：
- 城市使用 city_name
- 区域、商圈优先使用 region_name，也可以结合 community_name 或 detail_address
- 整租、不要合租优先使用 rent_type = 'whole_rent'
- 一居/两居/三居优先使用 rooms = 'one'/'two'/'three'
- 朝南/朝北/朝东/朝西优先使用 position = 'south'/'north'/'east'/'west'
- 独卫、厨房、阳台等设施优先使用 devices 的英文设备码，也可以结合 intro 模糊匹配

生产样例：
- rent_type=whole_rent, house_type=1室1厅1卫, rooms=one, position=south, devices 包含 toilet, cook, balcony
- rent_type=worry_free_rental, house_type=3室1厅2卫, rooms=three, position=south
"""

DANGEROUS_SQL_KEYWORDS = ["DROP", "DELETE", "UPDATE", "INSERT", "TRUNCATE", "ALTER"]
ALLOWED_SQL_COLUMNS = {
    "id",
    "user_id",
    "title",
    "rent_type",
    "floor",
    "all_floor",
    "house_type",
    "rooms",
    "position",
    "area",
    "price",
    "intro",
    "devices",
    "head_image",
    "images",
    "city_id",
    "city_name",
    "region_id",
    "region_name",
    "community_name",
    "detail_address",
    "longitude",
    "latitude",
}
SQL_TERM_ALIASES = {
    "朝南": ["朝南", "南", "south"],
    "朝北": ["朝北", "北", "north"],
    "朝东": ["朝东", "东", "east"],
    "朝西": ["朝西", "西", "west"],
    "一居": ["一居", "一居室", "一室", "一室一厅", "one", "1室"],
    "两居": ["两居", "两居室", "两室", "两室一厅", "two", "2室"],
    "三居": ["三居", "三居室", "三室", "三室一厅", "three", "3室"],
    "整租": ["整租", "whole_rent"],
    "不合租": ["不合租", "不要合租", "whole_rent"],
    "独卫": ["独卫", "toilet"],
    "卫生间": ["卫生间", "toilet"],
    "厨房": ["厨房", "cook", "gas"],
    "做饭": ["做饭", "cook", "gas"],
    "阳台": ["阳台", "balcony"],
    "冰箱": ["冰箱", "icebox"],
    "洗衣机": ["洗衣机", "washer"],
    "空调": ["空调", "aircondition"],
    "近地铁": ["近地铁", "地铁"],
}
PRODUCTION_ENUM_DISALLOWED_VALUES = {
    "rent_type": ["整租", "合租", "不合租", "不要合租"],
    "rooms": ["1", "2", "3", "一居", "一居室", "两居", "两居室", "三居", "三居室"],
    "position": ["朝南", "南", "朝北", "北", "朝东", "东", "朝西", "西"],
    "devices": ["独卫", "卫生间", "厨房", "做饭", "阳台", "冰箱", "洗衣机", "空调"],
}


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
    candidates = SQL_TERM_ALIASES.get(str(term), [str(term)])
    return any(values_match(candidate, sql) for candidate in candidates)


def extract_limit(sql: str) -> int | None:
    match = re.search(r"\blimit\s+(\d+)\b", sql, flags=re.IGNORECASE)
    if not match:
        return None
    return int(match.group(1))


def referenced_columns(sql: str) -> set[str]:
    sql_without_literals = re.sub(r"'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"", " ", sql)
    candidates = set()
    for pattern in [
        r"\bselect\s+(.*?)\s+from\b",
        r"\bwhere\s+(.*?)(?:\border\s+by\b|\blimit\b|$)",
        r"\border\s+by\s+(.*?)(?:\blimit\b|$)",
    ]:
        for match in re.finditer(pattern, sql_without_literals, flags=re.IGNORECASE):
            candidates.update(re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]*\b", match.group(1)))

    sql_keywords = {
        "and",
        "or",
        "not",
        "like",
        "between",
        "in",
        "is",
        "null",
        "asc",
        "desc",
        "as",
        "distinct",
        "count",
        "min",
        "max",
        "avg",
        "sum",
    }
    return {
        candidate.lower()
        for candidate in candidates
        if candidate.lower() not in sql_keywords and candidate != "*"
    }


def invalid_enum_literals(sql: str) -> list[dict]:
    invalid_literals = []
    normalized = normalize_sql(sql).replace("`", "")
    for column, disallowed_values in PRODUCTION_ENUM_DISALLOWED_VALUES.items():
        quoted_patterns = [
            rf"\b{column}\s*(?:=|!=|<>|like)\s*(['\"])(.*?)\1",
            rf"\b{column}\s+in\s*\((.*?)\)",
        ]
        values = []
        for pattern in quoted_patterns:
            for match in re.finditer(pattern, normalized, flags=re.IGNORECASE):
                if len(match.groups()) == 2:
                    values.append(match.group(2))
                else:
                    values.extend(re.findall(r"['\"](.*?)['\"]", match.group(1)))

        for match in re.finditer(
            rf"\b{column}\s*(?:=|!=|<>|like)\s*(\d+)\b",
            normalized,
            flags=re.IGNORECASE,
        ):
            values.append(match.group(1))

        for value in values:
            cleaned_value = value.strip("%")
            if cleaned_value in disallowed_values:
                invalid_literals.append({"column": column, "value": value})
    return invalid_literals


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

    columns = referenced_columns(normalized)
    unknown_columns = sorted(columns - ALLOWED_SQL_COLUMNS - {"houses"})
    if unknown_columns:
        failures.append("unknown_columns")

    enum_literal_failures = invalid_enum_literals(normalized)
    if enum_literal_failures:
        failures.append("invalid_enum_literals")

    # 只读安全必须严格通过；limit 数值和 should_include 属于约束质量，不属于安全性。
    safety_passed = not {"must_be_select", "must_have_limit", "must_not_include"} & set(failures)
    constraint_passed = (
        safety_passed
        and "limit" not in failures
        and not missing_must_include
        and not unknown_columns
        and not enum_literal_failures
    )
    full_passed = constraint_passed and not missing_should_include

    return {
        "must_be_select": must_be_select,
        "has_limit": has_limit,
        "expected_limit": expected_limit,
        "actual_limit": actual_limit,
        "missing_must_include": missing_must_include,
        "missing_should_include": missing_should_include,
        "found_forbidden": found_forbidden,
        "referenced_columns": sorted(columns),
        "unknown_columns": unknown_columns,
        "invalid_enum_literals": enum_literal_failures,
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
            "invalid_enum_literals": [],
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
