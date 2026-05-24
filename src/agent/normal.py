# 常规问答子图的构建与编译


from langgraph.constants import START, END
from langgraph.graph import StateGraph

from src.agent.common.context import ContextSchema
from src.agent.node.normal import normal_question_and_answer
from src.agent.state.normal import NormalState

normal_workflow = (
    StateGraph(NormalState, context_schema=ContextSchema)
    .add_node(normal_question_and_answer)
    .add_edge("__start__", "normal_question_and_answer")
    .compile(name="New Graph")
)
