import logging
from collections import Counter, defaultdict
from pathlib import Path

from agent.node.main import extract_user_intent
from tests.eval_scripts.common import (
    PROJECT_ROOT,
    base_summary,
    build_parser,
    load_cases,
    make_report_dir,
    require_env,
    write_json,
    write_jsonl,
)

EVAL_NAME = "intent"
DEFAULT_CASE_FILE = PROJECT_ROOT / "tests" / "eval_sets" / "intent_cases.jsonl"
LABELS = ["recommend", "reserve", "mine", "normal"]
logger = logging.getLogger(__name__)


def per_label_metrics(confusion: dict[str, Counter]) -> dict[str, dict]:
    metrics = {}
    for label in LABELS:
        tp = confusion[label][label]
        fp = sum(confusion[other][label] for other in LABELS if other != label)
        fn = sum(confusion[label][other] for other in LABELS if other != label)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        score = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        support = sum(confusion[label].values())
        predicted = sum(confusion[other][label] for other in LABELS)
        metrics[label] = {
            "precision": precision,
            "recall": recall,
            "f1": score,
            "support": support,
            "predicted": predicted,
        }
    return metrics


def macro_f1(label_metrics: dict[str, dict], *, observed_only: bool) -> float:
    selected = [
        values
        for values in label_metrics.values()
        if not observed_only or values["support"] or values["predicted"]
    ]
    if not selected:
        return 0.0
    return sum(values["f1"] for values in selected) / len(selected)


def run_eval(case_file: Path, output: Path | None, max_cases: int | None):
    require_env("DEEPSEEK_API_KEY")
    cases = load_cases(case_file, max_cases=max_cases)
    report_dir = make_report_dir(EVAL_NAME, output)

    rows = []
    failures = []
    confusion = defaultdict(Counter)

    for case in cases:
        expected = case["expected"]["intent"]
        try:
            actual = extract_user_intent(case["input"]).intent
            error = None
        except Exception as exc:
            actual = None
            error = repr(exc)

        passed = actual == expected
        confusion[expected][actual or "__error__"] += 1
        row = {
            "id": case["id"],
            "input": case["input"],
            "expected": expected,
            "actual": actual,
            "passed": passed,
            "error": error,
            "tags": case.get("tags", []),
            "difficulty": case.get("difficulty"),
        }
        rows.append(row)
        if not passed:
            failures.append(row)

    passed_count = sum(row["passed"] for row in rows)
    label_metrics = per_label_metrics(confusion)
    macro_f1_observed = macro_f1(label_metrics, observed_only=True)
    macro_f1_all = macro_f1(label_metrics, observed_only=False)
    summary = base_summary(EVAL_NAME, case_file, len(rows))
    summary.update(
        {
            "passed": passed_count,
            "failed": len(rows) - passed_count,
            "accuracy": passed_count / len(rows) if rows else 0.0,
            "macro_f1": macro_f1_observed,
            "macro_f1_observed_labels": macro_f1_observed,
            "macro_f1_all_labels": macro_f1_all,
            "per_label": label_metrics,
            "confusion_matrix": {
                label: {pred: confusion[label][pred] for pred in sorted(confusion[label])}
                for label in LABELS
            },
        }
    )

    write_json(report_dir / "summary.json", summary)
    write_jsonl(report_dir / "cases.jsonl", rows)
    write_jsonl(report_dir / "failures.jsonl", failures)
    logger.info("intent eval: %s/%s passed", passed_count, len(rows))
    logger.info("accuracy: %.4f, macro_f1: %.4f", summary["accuracy"], summary["macro_f1"])
    if summary["macro_f1"] != summary["macro_f1_all_labels"]:
        logger.info("macro_f1_all_labels: %.4f", summary["macro_f1_all_labels"])
    logger.info("report: %s", report_dir)


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = build_parser("评估用户意图识别准确率。", DEFAULT_CASE_FILE)
    args = parser.parse_args()
    run_eval(args.case_file, args.output, args.max_cases)


if __name__ == "__main__":
    main()
