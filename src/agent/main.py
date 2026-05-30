# 租房助手主图


from typing import Literal

from langgraph.graph import StateGraph

from agent.common.context import ContextSchema
from agent.node.main import determine_user_intent, query_mine, reserve_or_not
from agent.normal import normal_workflow
from agent.recommend import recommend_workflow
from agent.reserve import reserve_workflow
from agent.state.main import MainState, ReserveOrNot

graph = StateGraph(MainState, context_schema=ContextSchema)

graph.add_node(determine_user_intent)
graph.add_node("recommend", recommend_workflow)
graph.add_node("reserve", reserve_workflow)
graph.add_node("mine", query_mine)
graph.add_node("normal", normal_workflow)
graph.add_node(reserve_or_not)

graph.add_edge("__start__", "determine_user_intent")

def request_router(state: MainState) -> Literal["recommend", "reserve", "mine", "normal"]:
    # if state["user_intent"] == "recommend":
    #     return "recommend"
    # elif state["user_intent"] == "reserve":
    #     return "reserve"
    # elif state["user_intent"] == "mine":
    #     return "mine"
    # else:
    #     return "normal"
    return state["user_intent"]

graph.add_conditional_edges(
    "determine_user_intent",
    request_router,
    ["recommend", "reserve", "mine", "normal"]
)

def reserve_or_end(state: ReserveOrNot):
    if state["reserve_or_not"]:
        return "reserve"
    else:
        return "__end__"

graph.add_edge("recommend", "reserve_or_not")
graph.add_conditional_edges("reserve_or_not", reserve_or_end, ["reserve", "__end__"])
graph.add_edge("mine", "__end__")
graph.add_edge("reserve", "__end__")
graph.add_edge("normal", "__end__")

house_renting_agent = graph.compile()
