# reserve graph node


import uuid
from typing import Annotated, Any

from langchain_core.messages import SystemMessage
from langchain_core.tools import tool, InjectedToolArg
from langgraph.prebuilt import InjectedStore, ToolNode
from langgraph.runtime import Runtime
from langgraph.types import interrupt

from src.agent.common.context import ContextSchema
from src.agent.common.llm import model
from src.agent.common.store import Reservation, UserPreference
from src.agent.state.reserve import ReserveState

def get_reserve_house_name(state: ReserveState):
    reserve_house_name = interrupt("请输入你要预定的房源名称：")
    return {"reserve_house_name": reserve_house_name}

def get_user_name(state: ReserveState):
    user_name = interrupt("请输入你的名字：")
    return {"user_name": user_name}

def get_reserve_phone(state: ReserveState):
    reserve_phone = interrupt("请输入你的预订电话：")
    return {"reserve_phone": reserve_phone}

def get_user_ID_No(state: ReserveState):
    user_ID_No = interrupt("请输入你的身份证号码：")
    return {"user_ID_No": user_ID_No}

@tool
def create_order_tool(house_name: str, user_name: str, reserve_phone: str, ID_No: str,
                 runtime: Annotated[Any, InjectedToolArg()], store: Annotated[Any, InjectedStore()]):
    """
根据用户要预定的房源名称、用户名字、预订电话和身份证号码，生成订单信息

Args:
    house_name: 用户要预定的房源名称
    user_name: 用户名字
    reserve_phone: 用户预订电话
    ID_No: 用户身份证号码
    """

    order_id = str(uuid.uuid4())
    reservation = Reservation(
        order_id=order_id,
        house_name=house_name,
        phone_number=reserve_phone,
    )
    user_id = str(runtime.context.get("user_id"))
    namespace = (user_id,)
    preferences = store.search(namespace)
    if len(preferences) == 0:
        user_preference = UserPreference(reservations=[reservation])
        store.put(namespace, "preferences", user_preference.model_dump(exclude_none=True))
    else:
        pref = preferences[0].value or {}
        pref.setdefault("reservations", []).append(reservation.model_dump(exclude_none=True))
        store.put(namespace, "preferences", pref)
    return f"已下单，{order_id}，{house_name}"

create_order = ToolNode([create_order_tool], name="create_order")

from langchain_core.messages import SystemMessage, HumanMessage


def call_create_order_tool(state: ReserveState):
    messages = state.get("messages", [])
    # 获取历史记录中的最后一条消息
    last_message = messages[-1] if messages else None

    # 判断当前该调用工具还是总结结果
    if last_message and last_message.type == "tool":
        system_prompt = "请根据工具返回的订单结果，以亲切的口吻告知用户订单已成功生成，并提供订单号等信息。"
        ai_message = model.invoke([SystemMessage(content=system_prompt)] + messages)

    else:
        house_name = state.get("reserve_house_name")
        user_name = state.get("user_name")
        phone = state.get("reserve_phone")
        id_no = state.get("user_ID_No")

        instruction = (
            "我已经提供完所有预订信息，具体如下：\n"
            f"- 房源名称: {house_name}\n"
            f"- 入住姓名: {user_name}\n"
            f"- 预订电话: {phone}\n"
            f"- 身份证号: {id_no}\n\n"
            "请立即使用工具帮我下单。"
        )

        model_with_create_order_tool = model.bind_tools([create_order_tool], tool_choice="any")

        # 将构造的人类指令追加在对话最后
        instruction_msg = HumanMessage(content=instruction)
        invoke_messages = messages + [HumanMessage(content=instruction)]
        ai_message = model_with_create_order_tool.invoke(invoke_messages)

    return {"messages": [instruction_msg, ai_message]}