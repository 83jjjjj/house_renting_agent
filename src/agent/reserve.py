# 预订子图的构建与编译

from langgraph.constants import START, END
from langgraph.graph import StateGraph
from langgraph.prebuilt import tools_condition

from src.agent.common.context import ContextSchema
from src.agent.node.reserve import get_reserve_house_name, get_user_name, get_user_ID_No, get_reserve_phone, \
    call_create_order_tool, create_order
from src.agent.state.reserve import ReserveState

reserve_graph = StateGraph(ReserveState, context_schema=ContextSchema)

reserve_graph.add_sequence([get_reserve_house_name, get_user_name, get_reserve_phone, get_user_ID_No, call_create_order_tool])
reserve_graph.add_node("create_order", create_order)

reserve_graph.add_edge(START, "get_reserve_house_name")
reserve_graph.add_conditional_edges("call_create_order_tool", tools_condition, {"tools": "create_order", END: END})
reserve_graph.add_edge("create_order", "call_create_order_tool")

reserve_workflow = reserve_graph.compile()
