# recommend子图的构建和编译

from langgraph.constants import END, START
from langgraph.graph import StateGraph

from agent.common.context import ContextSchema
from agent.node.recommend import (
    call_schema_tool,
    check_sql,
    collect_user_demand,
    execute_query,
    generate_sql_query,
    get_schema,
    integrate_and_output,
    list_tables,
)
from agent.state.recommend import RecommendState

recommend_graph = StateGraph(RecommendState, context_schema=ContextSchema)

recommend_graph.add_node(collect_user_demand)
recommend_graph.add_node(list_tables)
recommend_graph.add_node(call_schema_tool)
recommend_graph.add_node(get_schema)
recommend_graph.add_node(generate_sql_query)
recommend_graph.add_node(check_sql)
recommend_graph.add_node(execute_query)
recommend_graph.add_node(integrate_and_output)

recommend_graph.add_edge(START, "collect_user_demand")
recommend_graph.add_edge("collect_user_demand", "list_tables")
recommend_graph.add_edge("list_tables", "call_schema_tool")
recommend_graph.add_edge("call_schema_tool", "get_schema")
recommend_graph.add_edge("get_schema", "generate_sql_query")
recommend_graph.add_edge("generate_sql_query", "check_sql")
recommend_graph.add_edge("check_sql", "execute_query")
recommend_graph.add_edge("execute_query", "integrate_and_output")
recommend_graph.add_edge("integrate_and_output", END)

recommend_workflow = recommend_graph.compile()
