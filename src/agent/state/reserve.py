# 预订子图的状态定义

from agent.state.main import MainState


class ReserveState(MainState):
    """预订子图的状态，
       继承了主状态的用户偏好，
       主要包含用户个人信息"""

    user_preferences: dict

    user_name: str
    reserve_phone: str
    user_ID_No: str

    reserve_house_name: str
