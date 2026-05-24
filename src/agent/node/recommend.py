# recommend graph node


from dotenv import load_dotenv

load_dotenv(verbose=True)

import os

from langchain_community.utilities import SQLDatabase
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel, Field

from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langgraph.runtime import Runtime
from langgraph.store.base import BaseStore
from langgraph.types import interrupt

from src.agent.common.llm import model
from src.agent.common.context import ContextSchema
from src.agent.state.recommend import RecommendState


class Demands(BaseModel):
    """用户的租房需求信息，主要用于结构化输出"""

    budget_min: float | None = Field(default=None, description="用户预算下限")
    budget_max: float | None = Field(default=None, description="用户预算上限")
    city: str | None = Field(default=None, description="租房所在城市，比如北京")
    area: str | None = Field(default=None, description="租房所在区县，比如朝阳")
    orientation: str | None = Field(default=None, description="房屋朝向，比如朝南")
    house_num: int | None = Field(default=None, description="房屋推荐数目")
    house_type: str | None = Field(default=None, description="房屋类型，比如一室一厅，主卧等")
    others: str | None = Field(default=None, description="其他要求，比如独卫、带厨房等")

default_demands = {
    "budget_min": 0.00,
    "budget_max": 10000.00,
    "city": "北京",
    "area": "朝阳",
    "orientation": "朝南",
    "house_num": 3,
    "house_type": "主卧",
    "others": "无"
}

preferences_dict = {
    "budget_min": "最低预算",
    "budget_max": "最高预算",
    "city": "城市",
    "area": "区县",
    "orientation": "房屋朝向",
    "house_num": "推荐房数",
    "house_type": "房间类型",
    "others": "其余偏好"
}

# 收集用户房源需求
def collect_user_demand(state: RecommendState, runtime: Runtime[ContextSchema], *, store: BaseStore):
    # 提取原则：有新值更新为新值，无则用旧值不动，再无则用默认值补充
    # 如果历史偏好有数据，先从中取
    demands = None
    user_id = runtime.context.get("user_id")
    namespace = (user_id,)
    preferences_key = "preferences"
    history_preferences = store.get(namespace, preferences_key)
    if user_id and history_preferences:
        demands = Demands(**history_preferences.value)
    else:
        demands = Demands()
    # 如果用户问话里有需求信息，尝试提取
    def info_extractor(user_message: HumanMessage):
        extract_info_sys_prompt = f"从以下提供的用户消息里，提取用户的租房偏好信息，没找到就给None，不可瞎猜或无中生有。\n"
        extracted_preferences = model.with_structured_output(Demands).invoke([
            SystemMessage(content=extract_info_sys_prompt),
            user_message
        ])
        # 一定要去掉None，否则update时会覆盖旧值为None
        return extracted_preferences.model_dump(exclude_none=True)

    final_demands = demands.model_dump()
    final_demands.update(info_extractor(state["messages"][-1]))
    # 如果需求信息不足，走中断，仍不足取默认值
    missing_info_list = []
    for pref in preferences_dict:
        if not final_demands.get(pref):
            missing_info_list.append(preferences_dict[pref])
    user_input = interrupt(f"为了提供更精准的服务，请提供以下关键信息：{missing_info_list}。您也可以选择‘不提供’，将开启默认服务")
    if user_input == "不提供":
        pass
    else:
        new_demands = info_extractor(HumanMessage(content=user_input))
        final_demands.update(new_demands)

    for info in final_demands:
        # 除了0，还可以除去""
        if not final_demands.get(info):
            final_demands[info] = default_demands[info]

    # 将新偏好数据存入store
    # 此处务必剔除None值，下方get的逻辑是key不存在采取default，为None则取None
    ori_pref_dict = demands.model_dump(exclude_none=True)
    # print(f'{ori_pref_dict.get("budget_min", default_demands["budget_min"])}, {final_demands["budget_min"]}')
    # print(f'{ori_pref_dict.get("budget_max", default_demands["budget_max"])}, {final_demands["budget_max"]}')
    # 预算范围只能往范围大的扩，涵盖更多房源
    updated_preferences = {
        **final_demands,
        "budget_min": min(ori_pref_dict.get("budget_min", default_demands["budget_min"]), final_demands["budget_min"]),
        "budget_max": max(ori_pref_dict.get("budget_max", default_demands["budget_max"]), final_demands["budget_max"]),
    }
    # 存入 store 保持持久化
    store.put(namespace, preferences_key, {
        "budget_min": updated_preferences["budget_min"],
        "budget_max": updated_preferences["budget_max"],
    })
    # 更新state
    return {
        "user_preferences": updated_preferences,
    }

db_user = os.getenv("DB_USER")
db_password = os.getenv("DB_PASSWORD")
db_host = os.getenv("DB_HOST")
db_port = os.getenv("DB_PORT")
db_name = os.getenv("DB_NAME")
db = SQLDatabase.from_uri(f"mysql+pymysql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}")

sql_toolkit = SQLDatabaseToolkit(db=db, llm=model)
sql_tools = sql_toolkit.get_tools()
# ['sql_db_query', 'sql_db_schema', 'sql_db_list_tables', 'sql_db_query_checker']
# print([tool.name for tool in sql_toolkit.get_tools()])

# next配合for+if精准取出第一个name符合条件的元素，可给上第二个参数在没找到时作默认值
query_tool = next(tool for tool in sql_tools if tool.name == "sql_db_query")
schema_tool = next(tool for tool in sql_tools if tool.name == "sql_db_schema")
list_tables_tool = next(tool for tool in sql_tools if tool.name == "sql_db_list_tables")
query_checker_tool = next(tool for tool in sql_tools if tool.name == "sql_db_query_checker")

# 手动调用工具，列出数据库里的所有表，供后续选择
def list_tables(state: RecommendState):
    tool_call = {
        "name": "sql_db_list_tables",
        "id": "123456",
        "args": {},
        "type": "tool_call",
    }
    ai_message_with_tool_calls = AIMessage(content="", tool_calls=[tool_call])
    tool_message = list_tables_tool.invoke(tool_call)
    ai_message_after_tool_call = AIMessage(content=f"可用的表：{tool_message.content}")
    return {"messages": [ai_message_with_tool_calls, tool_message, ai_message_after_tool_call]}

# 强制让llm生成tool_calls，判断要查询哪个表的schema
def call_schema_tool(state: RecommendState):
    # 强制模型走schema工具调用
    model_with_schema = model.bind_tools([schema_tool], tool_choice=True)
    tool_message = model_with_schema.invoke(state["messages"])
    return {"messages": tool_message}

# 获取schema
get_schema = ToolNode([schema_tool], name="get_schema")

# sql查询语句生成
def generate_sql_query(state: RecommendState):
    # 系统提示词由千问ai生成
    generate_sql_query_system_prompt = """
你是一个专业的 SQL 生成引擎。请根据对话历史中提供的数据库 Schema 以及当前的用户偏好信息，生成一条标准的 MySQL SELECT 查询语句。

### 核心指令
1. **仅输出 SQL**：直接返回 SQL 字符串，严禁包含 Markdown 格式（如 ```sql）、注释、换行符或任何解释性文字。
2. **严格遵循 Schema**：只能使用历史消息中已定义的表名和字段名，绝对禁止臆造不存在的列。
3. **逻辑映射规范**：
   - **数值范围**：处理预算时，正确使用 `>=`、`<=` 或 `BETWEEN`。
   - **模糊匹配**：对城市、区域、朝向等文本字段，统一使用 `LIKE '%关键词%'` 以确保召回率。
4. **安全性与限制**：
   - 必须包含 `LIMIT` 子句（默认为 {max_row}），防止一次性拉取过多数据。
   - 默认按价格升序 (`price ASC`) 或发布时间降序 (`id DESC`) 排序。

### 目标
输出一条语法正确、逻辑严密且可直接在 MySQL 中执行的 SELECT 语句。
    """
    system_prompt = generate_sql_query_system_prompt.format(max_row=state["user_preferences"]["house_num"])
    model_with_query_tool = model.bind_tools([query_tool], tool_choice=True)
    # 上一条消息是获取到schema的toolmessage
    ai_message_with_tool_calls = model_with_query_tool.invoke([SystemMessage(system_prompt)] + state["messages"])
    return {"messages": ai_message_with_tool_calls}

# sql语法检查
def check_sql(state: RecommendState):
    check_sql_system_prompt = """
你是一个严格的 MySQL 语法校验器。你的唯一任务是审查输入的 SQL SELECT 语句是否符合 MySQL 8.0 的标准语法规范。

### 审查标准
1. **基础语法**：检查关键字（SELECT, FROM, WHERE, AND, OR, LIMIT, ORDER BY 等）拼写是否正确，语句结构是否完整。
2. **符号匹配**：确保所有的单引号、双引号、圆括号 `()` 都能正确闭合，没有遗漏。
3. **标点规范**：检查逗号 `,`、分号 `;` 的使用位置是否恰当，是否存在多余或缺失的标点。
4. **函数与操作符**：确认使用的 SQL 函数（如 COUNT, MAX, LIKE 等）和比较操作符（=, >=, <=, BETWEEN 等）符合 MySQL 语法标准。
5. **严禁内容**：SQL 语句中绝对不能包含任何危险指令（如 DROP, DELETE, UPDATE, INSERT, TRUNCATE 等），只能包含 SELECT 查询。

### 输出要求
如果sql语句有语法错误，请重写查询。否则，复制原始查询，之后，调用合适的工具去执行查询。
"""
    system_prompt = check_sql_system_prompt
    model_with_query_tool = model.bind_tools([query_tool], tool_choice=True)
    tool_call = state["messages"][-1].tool_calls[0]
    sql = tool_call["args"]["query"]
    ai_message_with_tool_calls = model_with_query_tool.invoke([SystemMessage(system_prompt), HumanMessage(content=sql)])
    # id赋成上一个消息的，会覆盖式合并为同一个aimessage
    ai_message_with_tool_calls.id = state["messages"][-1].id
    return {"messages": ai_message_with_tool_calls}

# 执行sql
execute_query = ToolNode([query_tool], name="execute_query")

# 根据sql结果输出
def integrate_and_output(state: RecommendState):
    system_prompt = f"根据历史消息，向用户推荐房源。"
    ai_message = model.invoke([SystemMessage(content=system_prompt)] + state["messages"])
    return {"messages": ai_message}
