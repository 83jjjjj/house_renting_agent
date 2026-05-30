from types import SimpleNamespace

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from agent import main as graph_main
from agent.node import main as main_node
from agent.node import normal as normal_node
from agent.node import recommend as recommend_node
from agent.node import reserve as reserve_node


class FakeStoreValue:
    def __init__(self, value):
        self.value = value


class FakeStore:
    def __init__(self, value=None):
        self.value = value
        self.put_calls = []

    def get(self, namespace, key):
        if self.value is None:
            return None
        return FakeStoreValue(self.value)

    def put(self, namespace, key, value):
        self.put_calls.append((namespace, key, value))

    def search(self, namespace):
        if self.value is None:
            return []
        return [FakeStoreValue(self.value)]


class FakeStructuredModel:
    def __init__(self, model):
        self.model = model

    def invoke(self, messages):
        return self.model.structured_responses.pop(0)


class FakeModel:
    def __init__(self, structured_responses=None, invoke_response=None):
        self.structured_responses = structured_responses or []
        self.invoke_response = invoke_response or AIMessage(content="ok")
        self.invocations = []

    def with_structured_output(self, *args, **kwargs):
        return FakeStructuredModel(self)

    def invoke(self, messages):
        self.invocations.append(messages)
        return self.invoke_response


def test_determine_user_intent_routes_to_recommend(monkeypatch):
    fake_model = FakeModel(
        structured_responses=[main_node.UserIntent(intent="recommend")]
    )
    monkeypatch.setattr(main_node, "model", fake_model)

    result = main_node.determine_user_intent(
        {"messages": [HumanMessage(content="帮我推荐朝阳区的房子")]}
    )

    assert result == {"user_intent": "recommend"}


def test_normal_question_wraps_system_prompt(monkeypatch):
    fake_model = FakeModel(invoke_response=AIMessage(content="回答"))
    monkeypatch.setattr(normal_node, "model", fake_model)

    result = normal_node.normal_question_and_answer(
        {"messages": [HumanMessage(content="你好")]}
    )

    assert result["messages"].content == "回答"
    assert isinstance(fake_model.invocations[0][0], SystemMessage)


def test_query_mine_uses_preferences_and_reservations(monkeypatch):
    fake_model = FakeModel(invoke_response=AIMessage(content="你的订单如下"))
    store = FakeStore(
        {
            "budget_min": 3000.0,
            "budget_max": 9000.0,
            "reservations": [
                {
                    "order_id": "order-1",
                    "house_name": "阳光公寓",
                    "phone_number": "13800000000",
                    "city": "北京",
                    "area": "海淀",
                }
            ],
        }
    )
    runtime = SimpleNamespace(context={"user_id": "user-1"})
    monkeypatch.setattr(main_node, "model", fake_model)

    result = main_node.query_mine(
        {"messages": [HumanMessage(content="我之前订过哪些房子？")]},
        runtime,
        store=store,
    )

    assert result["messages"].content == "你的订单如下"
    system_prompt = fake_model.invocations[0][0].content
    assert "3000.0" in system_prompt
    assert "9000.0" in system_prompt
    assert "阳光公寓" in system_prompt


def test_reserve_or_not_routes_to_reserve(monkeypatch):
    monkeypatch.setattr(main_node, "interrupt", lambda _: "需要")

    assert main_node.reserve_or_not({"messages": []}) == {"reserve_or_not": True}


def test_reserve_or_not_routes_to_end(monkeypatch):
    monkeypatch.setattr(main_node, "interrupt", lambda _: "不需要")

    assert main_node.reserve_or_not({"messages": []}) == {"reserve_or_not": False}


def test_main_graph_router_helpers():
    assert graph_main.request_router({"user_intent": "mine"}) == "mine"
    assert graph_main.reserve_or_end({"reserve_or_not": True}) == "reserve"
    assert graph_main.reserve_or_end({"reserve_or_not": False}) == "__end__"


def test_collect_user_demand_preserves_reservations(monkeypatch):
    fake_model = FakeModel(
        structured_responses=[
            recommend_node.Demands(budget_min=3000.0, city="北京"),
            recommend_node.Demands(area="海淀", budget_max=9000.0),
        ]
    )
    store = FakeStore(
        {
            "budget_min": 5000.0,
            "budget_max": 8000.0,
            "reservations": [{"order_id": "order-1", "house_name": "旧订单"}],
        }
    )
    runtime = SimpleNamespace(context={"user_id": "user-1"})
    monkeypatch.setattr(recommend_node, "model", fake_model)
    monkeypatch.setattr(recommend_node, "interrupt", lambda _: "海淀，最高9000")

    result = recommend_node.collect_user_demand(
        {"messages": [HumanMessage(content="预算3000，北京")]}, runtime, store=store
    )

    assert result["user_preferences"]["budget_min"] == 3000.0
    assert result["user_preferences"]["budget_max"] == 9000.0
    assert result["user_preferences"]["city"] == "北京"
    assert result["user_preferences"]["area"] == "海淀"
    saved = store.put_calls[-1][2]
    assert saved["budget_min"] == 3000.0
    assert saved["budget_max"] == 9000.0
    assert saved["reservations"] == [{"order_id": "order-1", "house_name": "旧订单"}]


def test_collect_user_demand_fills_defaults_when_user_declines(monkeypatch):
    fake_model = FakeModel(structured_responses=[recommend_node.Demands()])
    store = FakeStore()
    runtime = SimpleNamespace(context={"user_id": "user-1"})
    monkeypatch.setattr(recommend_node, "model", fake_model)
    monkeypatch.setattr(recommend_node, "interrupt", lambda _: "不提供")

    result = recommend_node.collect_user_demand(
        {"messages": [HumanMessage(content="帮我推荐房子")]}, runtime, store=store
    )

    assert result["user_preferences"] == recommend_node.default_demands
    assert store.put_calls[-1][2] == {"budget_min": 0.0, "budget_max": 10000.0}


def test_reserve_interrupt_nodes(monkeypatch):
    replies = iter(["阳光公寓", "张三", "13800000000", "110101199001010000"])
    monkeypatch.setattr(reserve_node, "interrupt", lambda _: next(replies))

    assert reserve_node.get_reserve_house_name({}) == {"reserve_house_name": "阳光公寓"}
    assert reserve_node.get_user_name({}) == {"user_name": "张三"}
    assert reserve_node.get_reserve_phone({}) == {"reserve_phone": "13800000000"}
    assert reserve_node.get_user_ID_No({}) == {"user_ID_No": "110101199001010000"}


def test_call_create_order_tool_summarizes_tool_result(monkeypatch):
    fake_model = FakeModel(invoke_response=AIMessage(content="订单已生成"))
    monkeypatch.setattr(reserve_node, "model", fake_model)

    result = reserve_node.call_create_order_tool(
        {"messages": [ToolMessage(content="已下单，order-1，阳光公寓", tool_call_id="1")]}
    )

    assert result["messages"].content == "订单已生成"


def test_call_create_order_tool_requests_tool_call(monkeypatch):
    fake_bound_model = FakeModel(invoke_response=AIMessage(content="", tool_calls=[]))

    class FakeToolBindingModel(FakeModel):
        def bind_tools(self, tools, tool_choice=None):
            self.bound_tools = tools
            self.tool_choice = tool_choice
            return fake_bound_model

    fake_model = FakeToolBindingModel()
    monkeypatch.setattr(reserve_node, "model", fake_model)

    result = reserve_node.call_create_order_tool(
        {
            "messages": [HumanMessage(content="我要预订")],
            "reserve_house_name": "阳光公寓",
            "user_name": "张三",
            "reserve_phone": "13800000000",
            "user_ID_No": "110101199001010000",
        }
    )

    assert fake_model.tool_choice == "any"
    assert result["messages"][0].content.startswith("我已经提供完所有预订信息")
    assert "阳光公寓" in result["messages"][0].content
