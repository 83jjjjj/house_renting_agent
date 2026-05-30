import logging
import operator
import re
from typing import Annotated, Literal

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.store.memory import InMemoryStore
from langgraph.types import Command

from agent.common.context import ContextSchema
from agent.node import main as main_node
from agent.node import recommend as recommend_node
from agent.node import reserve as reserve_node
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

EVAL_NAME = "e2e"
DEFAULT_CASE_FILE = PROJECT_ROOT / "tests" / "eval_sets" / "e2e_cases.jsonl"
logger = logging.getLogger(__name__)


class E2EState(MessagesState, total=False):
    user_preferences: dict
    user_intent: Literal["recommend", "reserve", "mine", "normal"]
    reserve_or_not: bool
    user_name: str
    reserve_phone: str
    user_ID_No: str
    reserve_house_name: str
    visited: Annotated[list[str], operator.add]
    recommendation_emitted: bool
    query_used_store: bool
    normal_answered: bool


class FakeReserveModel:
    def bind_tools(self, tools, tool_choice=None):
        return self

    def invoke(self, messages):
        if messages and messages[-1].type == "tool":
            return AIMessage(content="订单已生成")

        instruction = messages[-1].content
        return AIMessage(
            content="",
            tool_calls=[
                {
                    "id": "call-1",
                    "name": "create_order_tool",
                    "args": {
                        "house_name": extract_instruction_value(instruction, "房源名称"),
                        "user_name": extract_instruction_value(instruction, "入住姓名"),
                        "reserve_phone": extract_instruction_value(instruction, "预订电话"),
                        "ID_No": extract_instruction_value(instruction, "身份证号"),
                    },
                }
            ],
        )


def extract_instruction_value(text: str, label: str) -> str:
    match = re.search(rf"{label}:\s*(.+)", text)
    return match.group(1).strip() if match else ""


def with_visit(name, updates: dict | None = None):
    result = dict(updates or {})
    result["visited"] = [name]
    return result


def determine_user_intent_node(state):
    result = main_node.determine_user_intent(state)
    return with_visit("determine_user_intent", result)


def collect_user_demand_node(state, runtime, *, store):
    result = recommend_node.collect_user_demand(state, runtime, store=store)
    return with_visit("collect_user_demand", result)


def simulated_recommend_node(state):
    return {
        "messages": [AIMessage(content="推荐结果：1. 阳光公寓；2. 星河公寓。")],
        "recommendation_emitted": True,
        "visited": ["recommend", "list_tables", "generate_sql_query", "integrate_and_output"],
    }


def reserve_or_not_node(state):
    result = main_node.reserve_or_not(state)
    return with_visit("reserve_or_not", result)


def query_mine_node(state, runtime, *, store):
    namespace = (str(runtime.context.get("user_id")),)
    preferences = store.get(namespace, "preferences")
    has_preferences = bool(preferences and preferences.value)
    return {
        "messages": [AIMessage(content="已查询用户偏好和预约记录。")],
        "query_used_store": has_preferences,
        "visited": ["query_mine"],
    }


def normal_question_and_answer_node(state):
    return {
        "messages": [AIMessage(content="普通问答已回复。")],
        "normal_answered": True,
        "visited": ["normal_question_and_answer"],
    }


def reserve_node_wrapper(fn):
    def wrapped(state):
        result = fn(state)
        return with_visit("reserve", result)

    return wrapped


def compile_e2e_graph(store):
    graph = StateGraph(E2EState, context_schema=ContextSchema)
    graph.add_node("determine_user_intent", determine_user_intent_node)
    graph.add_node("collect_user_demand", collect_user_demand_node)
    graph.add_node("recommend", simulated_recommend_node)
    graph.add_node("reserve_or_not", reserve_or_not_node)
    graph.add_node("query_mine", query_mine_node)
    graph.add_node("normal_question_and_answer", normal_question_and_answer_node)
    graph.add_node("get_reserve_house_name", reserve_node_wrapper(reserve_node.get_reserve_house_name))
    graph.add_node("get_user_name", reserve_node_wrapper(reserve_node.get_user_name))
    graph.add_node("get_reserve_phone", reserve_node_wrapper(reserve_node.get_reserve_phone))
    graph.add_node("get_user_ID_No", reserve_node_wrapper(reserve_node.get_user_ID_No))
    graph.add_node("call_create_order_tool", reserve_node_wrapper(reserve_node.call_create_order_tool))
    graph.add_node("create_order", ToolNode([reserve_node.create_order_tool]))

    graph.add_edge("__start__", "determine_user_intent")
    graph.add_conditional_edges(
        "determine_user_intent",
        lambda state: state["user_intent"],
        {
            "recommend": "collect_user_demand",
            "reserve": "get_reserve_house_name",
            "mine": "query_mine",
            "normal": "normal_question_and_answer",
        },
    )
    graph.add_edge("collect_user_demand", "recommend")
    graph.add_edge("recommend", "reserve_or_not")
    graph.add_conditional_edges(
        "reserve_or_not",
        lambda state: "reserve" if state["reserve_or_not"] else "__end__",
        {"reserve": "get_reserve_house_name", "__end__": "__end__"},
    )
    graph.add_edge("get_reserve_house_name", "get_user_name")
    graph.add_edge("get_user_name", "get_reserve_phone")
    graph.add_edge("get_reserve_phone", "get_user_ID_No")
    graph.add_edge("get_user_ID_No", "call_create_order_tool")
    graph.add_conditional_edges(
        "call_create_order_tool",
        tools_condition,
        {"tools": "create_order", "__end__": "__end__"},
    )
    graph.add_edge("create_order", "call_create_order_tool")
    graph.add_edge("query_mine", "__end__")
    graph.add_edge("normal_question_and_answer", "__end__")
    return graph.compile(checkpointer=InMemorySaver(), store=store)


def seed_store(store, user_id: str):
    store.put(
        (user_id,),
        "preferences",
        {
            "budget_min": 3000.0,
            "budget_max": 9000.0,
            "reservations": [
                {
                    "order_id": "seed-order-1",
                    "house_name": "阳光公寓",
                    "phone_number": "13800000000",
                }
            ],
        },
    )


def reservation_count(store, user_id: str) -> int:
    preferences = store.get((user_id,), "preferences")
    if not preferences or not preferences.value:
        return 0
    return len(preferences.value.get("reservations", []))


def run_case(graph, store, case: dict):
    user_id = f"eval-{case['id']}"
    seed_store(store, user_id)
    before_orders = reservation_count(store, user_id)
    config = {"configurable": {"thread_id": case["id"]}}
    turns = case["turns"]
    consumed_turns = 1
    interrupted_count = 0

    try:
        result = graph.invoke(
            {"messages": [HumanMessage(content=turns[0])]},
            config=config,
            context={"user_id": user_id},
        )
        while "__interrupt__" in result:
            interrupted_count += 1
            if consumed_turns >= len(turns):
                return result, {
                    "error": "missing_resume_turn",
                    "consumed_turns": consumed_turns,
                    "interrupted_count": interrupted_count,
                    "before_orders": before_orders,
                    "after_orders": reservation_count(store, user_id),
                }
            result = graph.invoke(
                Command(resume=turns[consumed_turns]),
                config=config,
                context={"user_id": user_id},
            )
            consumed_turns += 1
    except Exception as exc:
        return {}, {
            "error": repr(exc),
            "consumed_turns": consumed_turns,
            "interrupted_count": interrupted_count,
            "before_orders": before_orders,
            "after_orders": reservation_count(store, user_id),
        }

    return result, {
        "error": None,
        "consumed_turns": consumed_turns,
        "unused_turns": len(turns) - consumed_turns,
        "interrupted_count": interrupted_count,
        "before_orders": before_orders,
        "after_orders": reservation_count(store, user_id),
    }


def infer_final_route(result: dict, after_orders: int, before_orders: int) -> str | None:
    if after_orders > before_orders:
        return "reserve"
    return result.get("user_intent")


def score_case(case: dict, result: dict, run_meta: dict) -> dict:
    expected = case["expected"]
    visited = set(result.get("visited", []))
    failures = []

    final_route = infer_final_route(result, run_meta["after_orders"], run_meta["before_orders"])
    if expected.get("final_route") and final_route != expected["final_route"]:
        failures.append("final_route")

    missing_visits = [node for node in expected.get("must_visit", []) if node not in visited]
    if missing_visits:
        failures.append("must_visit")

    has_recommendation = bool(result.get("recommendation_emitted"))
    if expected.get("has_recommendation") is not None and has_recommendation != expected["has_recommendation"]:
        failures.append("has_recommendation")

    has_order = run_meta["after_orders"] > run_meta["before_orders"]
    if expected.get("has_order") is not None and has_order != expected["has_order"]:
        failures.append("has_order")

    uses_store = bool(result.get("query_used_store"))
    if expected.get("uses_store") is not None and uses_store != expected["uses_store"]:
        failures.append("uses_store")

    if run_meta.get("error"):
        failures.append("runtime_error")
    if run_meta.get("unused_turns", 0) != 0:
        failures.append("unused_turns")

    return {
        "final_route": final_route,
        "visited": sorted(visited),
        "missing_visits": missing_visits,
        "has_recommendation": has_recommendation,
        "has_order": has_order,
        "uses_store": uses_store,
        "failures": failures,
        "passed": not failures,
    }


def run_eval(case_file, output, max_cases):
    require_env("DEEPSEEK_API_KEY")
    previous_reserve_model = reserve_node.model
    reserve_node.model = FakeReserveModel()
    try:
        cases = load_cases(case_file, max_cases=max_cases)
        store = InMemoryStore()
        graph = compile_e2e_graph(store)
        report_dir = make_report_dir(EVAL_NAME, output)

        rows = []
        failures = []
        for case in cases:
            result, run_meta = run_case(graph, store, case)
            scores = score_case(case, result, run_meta)
            row = {
                "id": case["id"],
                "turns": case["turns"],
                "expected": case["expected"],
                "tags": case.get("tags", []),
                "difficulty": case.get("difficulty"),
                "run_meta": run_meta,
                **scores,
            }
            rows.append(row)
            if not row["passed"]:
                failures.append(row)

        total = len(rows)
        passed = sum(row["passed"] for row in rows)
        route_passed = sum("final_route" not in row["failures"] for row in rows)
        visit_passed = sum("must_visit" not in row["failures"] for row in rows)
        order_passed = sum("has_order" not in row["failures"] for row in rows)
        store_passed = sum("uses_store" not in row["failures"] for row in rows)
        summary = base_summary(EVAL_NAME, case_file, total)
        summary.update(
            {
                "passed": passed,
                "failed": total - passed,
                "task_success_rate": passed / total if total else 0.0,
                "route_success_rate": route_passed / total if total else 0.0,
                "must_visit_success_rate": visit_passed / total if total else 0.0,
                "order_check_success_rate": order_passed / total if total else 0.0,
                "store_check_success_rate": store_passed / total if total else 0.0,
            }
        )

        write_json(report_dir / "summary.json", summary)
        write_jsonl(report_dir / "cases.jsonl", rows)
        write_jsonl(report_dir / "failures.jsonl", failures)
        logger.info("e2e eval: %s/%s passed", passed, total)
        logger.info("task_success_rate: %.4f", summary["task_success_rate"])
        logger.info("report: %s", report_dir)
    finally:
        reserve_node.model = previous_reserve_model


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = build_parser("评估图级端到端多轮链路。", DEFAULT_CASE_FILE)
    args = parser.parse_args()
    run_eval(args.case_file, args.output, args.max_cases)


if __name__ == "__main__":
    main()
