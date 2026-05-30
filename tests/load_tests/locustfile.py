import json

from locust import HttpUser, between, task


class LangGraphUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        response = self.client.post("/threads", json={})
        response.raise_for_status()
        self.thread_id = response.json()["thread_id"]

    def stream_run(self, payload):
        with self.client.post(
            f"/threads/{self.thread_id}/runs/stream",
            json=payload,
            stream=True,
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"HTTP {response.status_code}: {response.text}")
                return

            for line in response.iter_lines():
                if not line:
                    continue
                if line.startswith(b"data: "):
                    data = line[6:]
                    if data.strip():
                        json.loads(data)
            response.success()

    @task(5)
    def normal_question(self):
        self.stream_run(
            {
                "assistant_id": "house_renting_agent",
                "input": {
                    "messages": [
                        {"role": "human", "content": "北京租房签合同要注意什么？"}
                    ]
                },
                "context": {"user_id": "load-test-user"},
                "stream_mode": ["updates", "messages"],
            }
        )

    @task(3)
    def recommend_house(self):
        self.stream_run(
            {
                "assistant_id": "house_renting_agent",
                "input": {
                    "messages": [
                        {"role": "human", "content": "推荐北京朝阳5000以内的主卧"}
                    ]
                },
                "context": {"user_id": "load-test-user"},
                "stream_mode": ["updates", "messages"],
            }
        )
