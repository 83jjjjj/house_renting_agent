import os
from functools import lru_cache

from langchain_openai import ChatOpenAI


@lru_cache(maxsize=1)
def get_model():
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("缺少 DEEPSEEK_API_KEY，无法调用 LLM。")

    return ChatOpenAI(
        temperature=0,
        model="deepseek-v4-flash",
        openai_api_key=api_key,
        openai_api_base="https://api.deepseek.com",
        extra_body={
            "thinking": {
                "type": "disabled"
            }
        }
    )


class LazyChatModel:
    def __getattr__(self, name):
        return getattr(get_model(), name)


model = LazyChatModel()
