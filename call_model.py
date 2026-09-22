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
    run_id = None

    def capture_run(metadata):
        nonlocal run_id
        run_id = metadata["run_id"]

    try:
        result = client.runs.wait(
            None,  # Stateless run; use a thread ID for conversation history.
            "docs_agent",
            input={"messages": [{"role": "user", "content": question}]},
            on_run_created=capture_run,
        )
        message = result["messages"][-1]
        content = message["content"]
        if isinstance(content, list):
            return content[0]["text"]
        return content
    except Exception:
        print(f"Failed run ID: {run_id}")
        raise


if __name__ == "__main__":
    print(call_model("what is langchain"))
