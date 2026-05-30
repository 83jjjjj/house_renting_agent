from types import SimpleNamespace

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

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


def test_call_create_order_tool_summarizes_tool_result(monkeypatch):
    fake_model = FakeModel(invoke_response=AIMessage(content="订单已生成"))
    monkeypatch.setattr(reserve_node, "model", fake_model)

    result = reserve_node.call_create_order_tool(
        {"messages": [ToolMessage(content="已下单，order-1，阳光公寓", tool_call_id="1")]}
    )

    assert result["messages"].content == "订单已生成"
