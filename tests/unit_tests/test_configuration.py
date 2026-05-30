from langgraph.pregel import Pregel

from agent import (
    house_renting_agent,
    normal_workflow,
    recommend_workflow,
    reserve_workflow,
)


def test_graphs_are_compiled() -> None:
    assert isinstance(house_renting_agent, Pregel)
    assert isinstance(recommend_workflow, Pregel)
    assert isinstance(reserve_workflow, Pregel)
    assert isinstance(normal_workflow, Pregel)
