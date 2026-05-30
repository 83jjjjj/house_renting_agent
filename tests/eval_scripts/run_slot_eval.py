import logging
from pathlib import Path

from agent.node.recommend import extract_user_demand_fields
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

EVAL_NAME = "slot"
DEFAULT_CASE_FILE = PROJECT_ROOT / "tests" / "eval_sets" / "slot_cases.jsonl"
logger = logging.getLogger(__name__)


def score_case(expected: dict, actual: dict):
    expected_fields = set(expected)
    actual_fields = {key for key, value in actual.items() if value is not None}
    matched_fields = {
        key for key in expected_fields if key in actual_fields and values_match(expected[key], actual[key])
    }

    false_positive_fields = actual_fields - expected_fields
    false_negative_fields = expected_fields - matched_fields
    wrong_fields = {
        key
        for key in expected_fields & actual_fields
        if key not in matched_fields
    }

    return {
        "matched_fields": sorted(matched_fields),
        "false_positive_fields": sorted(false_positive_fields),
        "false_negative_fields": sorted(false_negative_fields),
        "wrong_fields": sorted(wrong_fields),
        "tp": len(matched_fields),
        "fp": len(false_positive_fields) + len(wrong_fields),
        "fn": len(false_negative_fields),
        "required_fields_passed": not false_negative_fields and not wrong_fields,
        "exact_match": not false_positive_fields and not false_negative_fields and not wrong_fields,
    }


def run_eval(case_file: Path, output: Path | None, max_cases: int | None):
    require_env("DEEPSEEK_API_KEY")
    cases = load_cases(case_file, max_cases=max_cases)
    report_dir = make_report_dir(EVAL_NAME, output)

    rows = []
    failures = []
    total_tp = 0
    total_fp = 0
    total_fn = 0
    exact_match_count = 0
    required_match_count = 0

    for case in cases:
        expected = case["expected"]
        try:
            actual = extract_user_demand_fields(case["input"])
            error = None
        except Exception as exc:
            actual = {}
            error = repr(exc)

        scores = score_case(expected, actual)
        total_tp += scores["tp"]
        total_fp += scores["fp"]
        total_fn += scores["fn"]
        exact_match_count += int(scores["exact_match"])
        required_match_count += int(scores["required_fields_passed"])

        row = {
            "id": case["id"],
            "input": case["input"],
            "expected": expected,
            "actual": actual,
            "passed": scores["exact_match"],
            "error": error,
            "tags": case.get("tags", []),
            "difficulty": case.get("difficulty"),
            **scores,
        }
        rows.append(row)
        if not row["passed"]:
            failures.append(row)

    precision = total_tp / (total_tp + total_fp) if total_tp + total_fp else 0.0
    recall = total_tp / (total_tp + total_fn) if total_tp + total_fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0

    summary = base_summary(EVAL_NAME, case_file, len(rows))
    summary.update(
        {
            "exact_match": exact_match_count,
            "exact_match_rate": exact_match_count / len(rows) if rows else 0.0,
            "required_fields_match": required_match_count,
            "required_fields_match_rate": required_match_count / len(rows) if rows else 0.0,
            "field_precision": precision,
            "field_recall": recall,
            "field_f1": f1,
            "tp": total_tp,
            "fp": total_fp,
            "fn": total_fn,
        }
    )

    write_json(report_dir / "summary.json", summary)
    write_jsonl(report_dir / "cases.jsonl", rows)
    write_jsonl(report_dir / "failures.jsonl", failures)
    write_jsonl(
        report_dir / "required_failures.jsonl",
        (row for row in rows if not row["required_fields_passed"]),
    )
    logger.info(
        "slot eval: %s/%s strict exact matches, %s/%s required-field matches",
        exact_match_count,
        len(rows),
        required_match_count,
        len(rows),
    )
    logger.info(
        "field_precision: %.4f, field_recall: %.4f, field_f1: %.4f",
        precision,
        recall,
        f1,
    )
    logger.info("report: %s", report_dir)


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = build_parser("评估租房需求槽位抽取效果。", DEFAULT_CASE_FILE)
    args = parser.parse_args()
    run_eval(args.case_file, args.output, args.max_cases)


if __name__ == "__main__":
    main()
