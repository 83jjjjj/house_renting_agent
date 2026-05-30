# normal graph node

from langchain_core.messages import SystemMessage

from agent.common.llm import model
from agent.state.normal import NormalState


def normal_question_and_answer(state: NormalState):
    system_prompt = "你是个问答助手。根据历史消息，回答用户的问题。"
    ai_message = model.invoke([SystemMessage(content=system_prompt)] + state["messages"])
    return {"messages": ai_message}
