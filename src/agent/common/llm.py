import os

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

# model = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)

model = ChatOpenAI(
    temperature=0,
    model="deepseek-v4-flash",
    openai_api_key=os.getenv("DEEPSEEK_API_KEY"),
    openai_api_base="https://api.deepseek.com",
    extra_body={
            "thinking": {
                "type": "disabled"
            }
    }
)
