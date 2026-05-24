# 主图状态定义


from typing import Literal, TypedDict

from langgraph.graph import MessagesState


class MainState(MessagesState):
    """主图状态定义"""

    # 用户偏好，此处指用户预算范围
    user_preferences: dict
    user_intent: Literal["recommend", "reserve", "mine", "normal"]

class ReserveOrNot(TypedDict):
    reserve_or_not: bool
