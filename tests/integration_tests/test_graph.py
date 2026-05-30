import os

import pytest
from langchain_core.messages import HumanMessage

from agent import normal_workflow

pytestmark = pytest.mark.anyio


@pytest.mark.skipif(
    os.getenv("RUN_LIVE_LLM_TESTS") != "1",
    reason="live LLM integration tests require RUN_LIVE_LLM_TESTS=1 and provider credentials",
)
async def test_normal_graph_live_llm_smoke() -> None:
    result = await normal_workflow.ainvoke(
        {"messages": [HumanMessage(content="用一句话说你好")]}
    )
    assert result["messages"][-1].content
