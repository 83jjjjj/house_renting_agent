# main graph


from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.runtime import Runtime
from langgraph.store.base import BaseStore
from langgraph.types import interrupt
from pydantic import BaseModel, Field

from agent.common.context import ContextSchema
from agent.common.llm import model
from agent.state.main import MainState, ReserveOrNot


# 用于llm的结构化输出用户意图
class UserIntent(BaseModel):
    """用于判别用户意图"""

    intent: Literal["recommend", "reserve", "mine", "normal"] = Field(..., description="用户意图只能是推荐房源、预订房源、查询我的和常规问答中的一种")


USER_INTENT_SYSTEM_PROMPT = (
    "你是能通过理解语义来识别用户意图的专家。"
    "请根据用户消息，判别用户意图。"
)


def extract_user_intent(user_message: HumanMessage | str) -> UserIntent:
    if isinstance(user_message, str):
        user_message = HumanMessage(content=user_message)

    return model.with_structured_output(UserIntent, method="function_calling").invoke(
        [SystemMessage(content=USER_INTENT_SYSTEM_PROMPT), user_message]
    )


# 识别用户意图，进行请求路由
def determine_user_intent(state: MainState):
    user_intent = extract_user_intent(state["messages"][-1])
    return {"user_intent": user_intent.intent}

# 查询用户历史
def query_mine(state: MainState, runtime: Runtime[ContextSchema], *, store: BaseStore):
    user_id = runtime.context["user_id"]
    namespace = (user_id,)
    preferences = store.get(namespace, "preferences").value or {}
    reservations = preferences.get("reservations", [])
    reservations_info = ""

    if reservations:
        for reservation in reservations:
            reservations_info += (f"订单id：{reservation.get('order_id', '无')}\n"
                                  f"房源名称：{reservation.get('house_name', '无')}\n"
                                  f"房源预订电话：{reservation.get('phone_number', '无')}\n"
                                  f"价格，单位为元/月：{reservation.get('price', '无')}\n"
                                  f"房源详细信息：{reservation.get('house_description', '无')}\n"
                                  f"房子所在城市：{reservation.get('city', '无')}\n"
                                  f"房子所在区县：{reservation.get('area', '无')}\n")
    else:
        reservations_info = "无"

    query_mine_system_prompt = f"""
你是知悉用户个人偏好和租房历史的助手。
用户的偏好信息：1. 最低预算：{preferences.get('budget_min', '无')}
             2. 最高预算：{preferences.get('budget_max', '无')}
             3. 用户的租房历史：{reservations_info}
注意，如果可以结合上述信息，务必使用到。如果提问与其无关，则直接回复即可。
"""
    ai_message = model.invoke([SystemMessage(content=query_mine_system_prompt), state["messages"][-1]])
    return {"messages": ai_message}

# 中断询问用户是否需要预订
def reserve_or_not(state: MainState) -> ReserveOrNot:
    choice = interrupt("请问，是否需要帮助您预订房源？\n"
                       "如果需要，请回复'**需要**'。\n"
                       "如果不需要，请回复'**不需要**'。\n")
    if choice == "需要":
        return ReserveOrNot(reserve_or_not=True)
    else:
        return ReserveOrNot(reserve_or_not=False)
