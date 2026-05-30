from types import SimpleNamespace

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.store.memory import InMemoryStore
from langgraph.types import Command

from agent.common.context import ContextSchema
from agent.node import main as main_node
from agent.node import normal as normal_node
from agent.node import reserve as reserve_node
from agent.state.main import MainState, ReserveOrNot
from agent.state.reserve import ReserveState


class FakeStructuredModel:
    def __init__(self, response):
        self.response = response

    def invoke(self, messages):
        return self.response


class FakeModel:
    def __init__(self, *, intent="normal", response="ok"):
        self.intent = intent
        self.response = response
        self.invocations = []

    def with_structured_output(self, schema, method=None):
        return FakeStructuredModel(main_node.UserIntent(intent=self.intent))

    def invoke(self, messages):
        self.invocations.append(messages)
        return AIMessage(content=self.response)


def compile_test_main_graph(store=None):
    graph = StateGraph(MainState, context_schema=ContextSchema)
    graph.add_node(main_node.determine_user_intent)
    graph.add_node("mine", main_node.query_mine)
    graph.add_node("normal", normal_node.normal_question_and_answer)

    graph.add_edge("__start__", "determine_user_intent")
    graph.add_conditional_edges(
        "determine_user_intent",
        lambda state: state["user_intent"],
        ["mine", "normal"],
    )
    graph.add_edge("mine", "__end__")
    graph.add_edge("normal", "__end__")
    return graph.compile(store=store)


def compile_test_reserve_graph(store=None):
    graph = StateGraph(ReserveState, context_schema=ContextSchema)
    graph.add_sequence(
        [
            reserve_node.get_reserve_house_name,
            reserve_node.get_user_name,
            reserve_node.get_reserve_phone,
            reserve_node.get_user_ID_No,
            reserve_node.call_create_order_tool,
        ]
    )
    graph.add_node("create_order", ToolNode([reserve_node.create_order_tool]))
    graph.add_edge("__start__", "get_reserve_house_name")
    graph.add_conditional_edges(
        "call_create_order_tool",
        tools_condition,
        {"tools": "create_order", "__end__": "__end__"},
    )
    graph.add_edge("create_order", "call_create_order_tool")
    return graph.compile(checkpointer=InMemorySaver(), store=store)


def compile_reserve_or_end_graph():
    graph = StateGraph(ReserveOrNot)
    graph.add_node("reserve_or_not", main_node.reserve_or_not)
    graph.add_edge("__start__", "reserve_or_not")
    graph.add_conditional_edges(
        "reserve_or_not",
        lambda state: "reserve" if state["reserve_or_not"] else "__end__",
        {"reserve": "reserve", "__end__": "__end__"},
    )
    graph.add_node("reserve", lambda state: {"reserve_or_not": True})
    graph.add_edge("reserve", "__end__")
    return graph.compile(checkpointer=InMemorySaver())


def test_main_graph_routes_to_mine_and_reads_store(monkeypatch):
    store = InMemoryStore()
    store.put(
        ("user-1",),
        "preferences",
        {
            "budget_min": 3000.0,
            "budget_max": 9000.0,
            "reservations": [{"order_id": "order-1", "house_name": "阳光公寓"}],
        },
    )
    fake_model = FakeModel(intent="mine", response="查询完成")
    monkeypatch.setattr(main_node, "model", fake_model)

    graph = compile_test_main_graph(store=store)
    result = graph.invoke(
        {"messages": [HumanMessage(content="我之前订过哪些房子？")]},
        context={"user_id": "user-1"},
    )

    assert result["user_intent"] == "mine"
    assert result["messages"][-1].content == "查询完成"
    assert "阳光公寓" in fake_model.invocations[-1][0].content


def test_main_graph_routes_to_normal(monkeypatch):
    fake_model = FakeModel(intent="normal", response="普通回答")
    monkeypatch.setattr(main_node, "model", fake_model)
    monkeypatch.setattr(normal_node, "model", fake_model)

    graph = compile_test_main_graph()
    result = graph.invoke(
        {"messages": [HumanMessage(content="租房合同要注意什么？")]},
        context={"user_id": "user-1"},
    )

    assert result["user_intent"] == "normal"
    assert result["messages"][-1].content == "普通回答"


def test_reserve_or_not_interrupt_resume_to_reserve():
    graph = compile_reserve_or_end_graph()
    config = {"configurable": {"thread_id": "reserve-choice"}}

    interrupted = graph.invoke({}, config=config)
    assert "__interrupt__" in interrupted
    assert "是否需要帮助您预订房源" in interrupted["__interrupt__"][0].value

    result = graph.invoke(Command(resume="需要"), config=config)
    assert result["reserve_or_not"] is True


def test_reserve_graph_collects_inputs_and_writes_order(monkeypatch):
    store = InMemoryStore()

    class FakeToolCallingModel:
        def bind_tools(self, tools, tool_choice=None):
            return SimpleNamespace(
                invoke=lambda messages: AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "id": "call-1",
                            "name": "create_order_tool",
                            "args": {
                                "house_name": "阳光公寓",
                                "user_name": "张三",
                                "reserve_phone": "13800000000",
                                "ID_No": "110101199001010000",
                            },
                        }
                    ],
                )
            )

        def invoke(self, messages):
            return AIMessage(content="订单已生成")

    monkeypatch.setattr(reserve_node, "model", FakeToolCallingModel())

    graph = compile_test_reserve_graph(store=store)
    config = {"configurable": {"thread_id": "reserve-flow"}}

    result = graph.invoke({}, config=config, context={"user_id": "user-1"})
    assert "__interrupt__" in result

    for value in ["阳光公寓", "张三", "13800000000", "110101199001010000"]:
        result = graph.invoke(
            Command(resume=value),
            config=config,
            context={"user_id": "user-1"},
        )

    assert result["messages"][-1].content == "订单已生成"
    preferences = store.get(("user-1",), "preferences").value
    assert preferences["reservations"][0]["house_name"] == "阳光公寓"
    assert preferences["reservations"][0]["phone_number"] == "13800000000"
