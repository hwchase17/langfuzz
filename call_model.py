from functools import cache

import httpx
from langgraph_sdk import get_sync_client

url = "https://chat-langchain-external-707c6e45e5075e168a6835a7d23a9934.us.langgraph.app"


@cache
def get_client():
    response = httpx.post(f"{url}/identity/guest", timeout=30)
    response.raise_for_status()
    token = response.json()["token"]
    return get_sync_client(
        url=url,
        headers={"Authorization": f"Bearer {token}"},
    )


def call_model(question: str) -> str:
    client = get_client()
    result = client.runs.wait(
        None,  # Stateless run; use a thread ID for conversation history.
        "docs_agent",
        input={"messages": [{"role": "user", "content": question}]},
    )
    return result["messages"][-1]["content"]


if __name__ == "__main__":
    print(call_model("what is langchain"))
