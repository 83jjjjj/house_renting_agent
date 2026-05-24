import unittest
from unittest.mock import MagicMock, patch
from agent.node.recommend import collect_user_demand, Demands, default_demands
from langchain_core.messages import HumanMessage


class TestCollectUserDemandFinal(unittest.TestCase):

    def setUp(self):
        """在每个测试前准备通用的模拟环境"""
        self.mock_store = MagicMock()
        # 模拟历史偏好：假设用户之前存过 预算下限5000，上限12000，城市是上海
        mock_get_result = MagicMock()
        mock_get_result.value = {"budget_min": 5000.0, "budget_max": 12000.0, "city": "上海"}
        self.mock_store.get.return_value = mock_get_result

        self.mock_runtime = MagicMock()
        self.mock_runtime.context = {"user_id": "user_test_001"}

        self.mock_state = {
            "messages": [HumanMessage(content="帮我推荐一套房子")]
        }

    @patch('agent.node.recommend.model')
    @patch('agent.node.recommend.interrupt')
    def test_scenario_choose_default(self, mock_interrupt, mock_model):
        """测试场景一：用户在中断时选择'不提供'，验证默认值填充及预算极值计算"""

        # 1. 模拟用户选择“不提供”
        mock_interrupt.return_value = "不提供"

        # 2. 模拟 LLM 从初始消息中提取到了一个新的预算下限 4000 (比历史的 5000 更低)
        # 预期结果：min(5000, 4000) = 4000，max(12000, 默认10000) = 12000
        fake_extracted = Demands(budget_min=4000.0, budget_max=None, city=None)
        mock_model.with_structured_output.return_value.invoke.return_value = fake_extracted

        # 3. 执行逻辑
        result = collect_user_demand(self.mock_state, self.mock_runtime, store=self.mock_store)

        # 4. 断言结果
        # 预算下限应该取了最小值 4000
        self.assertEqual(result["budget_min"], 4000.0)
        # 预算上限因为没提供，应该保持历史的 12000 (不会被默认值覆盖，因为不是 None/空)
        self.assertEqual(result["budget_max"], 12000.0)
        # 城市没提供，且历史有“上海”，应该保留“上海”
        self.assertEqual(result["city"], "上海")
        # 朝向没提供，应该填充默认值“朝南”
        self.assertEqual(result["orientation"], default_demands["orientation"])

        # 5. 验证 store.put 被调用，且存入了计算后的极值
        self.assertTrue(self.mock_store.put.called)
        saved_data = self.mock_store.put.call_args[0][2]
        self.assertEqual(saved_data["budget_min"], 4000.0)
        self.assertEqual(saved_data["budget_max"], 12000.0)

    @patch('agent.node.recommend.model')
    @patch('agent.node.recommend.interrupt')
    def test_scenario_provide_new_info(self, mock_interrupt, mock_model):
        """测试场景二：用户在中断时提供了新信息，验证覆盖逻辑与预算极值计算"""

        # 1. 模拟用户提供了具体的补充信息
        mock_interrupt.return_value = "我要找北京朝阳区的，预算最高一万五"

        # 2. 模拟两次 LLM 调用：
        # 第一次：从初始消息提取（为空）
        # 第二次：从中断回复提取（提取到 city=北京, area=朝阳, budget_max=15000）
        mock_model.with_structured_output.return_value.invoke.side_effect = [
            Demands(),  # 第一次为空
            Demands(city="北京", area="朝阳", budget_max=15000.0)  # 第二次有新数据
        ]

        # 3. 执行逻辑
        result = collect_user_demand(self.mock_state, self.mock_runtime, store=self.mock_store)

        # 4. 断言结果
        # 城市和区域应该被新提供的信息覆盖
        self.assertEqual(result["city"], "北京")
        self.assertEqual(result["area"], "朝阳")

        # 预算上限：历史是 12000，新提供 15000，max 应该取 15000
        self.assertEqual(result["budget_max"], 15000.0)

        # 预算下限：历史是 5000，新没提供，应该保持 5000
        self.assertEqual(result["budget_min"], 5000.0)

        # 5. 验证 store.put 存入了正确的极值
        saved_data = self.mock_store.put.call_args[0][2]
        self.assertEqual(saved_data["budget_max"], 15000.0)


if __name__ == '__main__':
    unittest.main()