import argparse
import json
import os
import re
import subprocess
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPORT_ROOT = PROJECT_ROOT / "reports" / "eval"
TIMEZONE = ZoneInfo("Asia/Shanghai")


def build_parser(description: str, default_case_file: Path) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--case-file",
        type=Path,
        default=default_case_file,
        help="JSONL 测试集路径。",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="报告输出目录。默认写入 reports/eval/<timestamp>_<commit>_<eval-name>。",
    )
    parser.add_argument(
        "--max-cases",
        type=int,
        default=None,
        help="只跑前 N 条样本，便于快速冒烟。",
    )
    return parser


def load_cases(path: Path, max_cases: int | None = None) -> list[dict]:
    cases = []
    with path.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            if not line.strip():
                continue
            case = json.loads(line)
            case["_line_no"] = line_no
            cases.append(case)
            if max_cases is not None and len(cases) >= max_cases:
                break
    return cases


def require_env(var_name: str):
    load_dotenv()
    if not os.getenv(var_name):
        raise SystemExit(
            f"缺少环境变量 {var_name}。请先复制 .env.example 为 .env 并配置 {var_name}。"
        )


def current_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"
    return result.stdout.strip()


def make_report_dir(eval_name: str, output: Path | None) -> Path:
    if output:
        report_dir = output
    else:
        timestamp = datetime.now(TIMEZONE).strftime("%Y-%m-%d_%H%M%S")
        report_dir = DEFAULT_REPORT_ROOT / f"{timestamp}_{current_commit()}_{eval_name}"
    report_dir.mkdir(parents=True, exist_ok=True)
    return report_dir


def write_json(path: Path, data: dict):
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def write_jsonl(path: Path, rows: Iterable[dict]):
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def base_summary(eval_name: str, case_file: Path, total: int) -> dict:
    return {
        "eval_name": eval_name,
        "case_file": str(case_file),
        "commit": current_commit(),
        "created_at": datetime.now(TIMEZONE).isoformat(),
        "total": total,
    }


def normalize_text(value):
    if value is None:
        return None
    return str(value).strip().lower().replace(" ", "")


def is_empty_value(value) -> bool:
    normalized = normalize_text(value)
    return normalized in {None, "", "none", "null", "无", "不限", "无所谓", "不限制"}


def split_expected_terms(value) -> list[str]:
    normalized = normalize_text(value)
    if not normalized:
        return []
    return [term for term in re.split(r"[，,、;；]+", normalized) if term]


def values_match(expected, actual) -> bool:
    if expected is None:
        return actual is None
    if actual is None:
        return False
    if isinstance(expected, int | float):
        try:
            return float(actual) == float(expected)
        except (TypeError, ValueError):
            return False

    expected_text = normalize_text(expected)
    actual_text = normalize_text(actual)
    expected_terms = split_expected_terms(expected)
    if len(expected_terms) > 1:
        return all(term in actual_text for term in expected_terms)
    return expected_text == actual_text or expected_text in actual_text
