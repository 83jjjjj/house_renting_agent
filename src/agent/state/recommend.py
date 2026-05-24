# 推荐子图的状态定义

from src.agent.state.main import MainState


class RecommendState(MainState):
    """推荐子图的状态，
       继承了主状态的用户偏好，
       主要包含用户房源需求"""

    user_preferences: dict
