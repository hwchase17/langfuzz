import httpx
from langgraph_sdk import get_sync_client

url = "https://chat-langchain-external-707c6e45e5075e168a6835a7d23a9934.us.langgraph.app"


def get_client():
    response = httpx.post(f"{url}/identity/guest", timeout=30)
    response.raise_for_status()
    token = response.json()["token"]
    return get_sync_client(
        url=url,
        headers={"Authorization": f"Bearer {token}"},
    )


def call_model(question: str) -> dict[str, str | None]:
    client = get_client()
    thread = client.threads.create()
    run_id = None

    def capture_run(metadata):
        nonlocal run_id
        run_id = metadata["run_id"]

    result = client.runs.wait(
        thread["thread_id"],
        "docs_agent",
        input={"messages": [{"role": "user", "content": question}]},
        on_run_created=capture_run,
    )
    if not result.get("messages"):
        state = client.threads.get_state(thread["thread_id"])
        result = state["values"]

    try:
        message = result["messages"][-1]
        content = message["content"]
        if isinstance(content, list):
            content = content[0]["text"]
        return {"answer": content, "trace_id": run_id}
    except Exception:
        print(result)
        print(f"Failed run ID: {run_id}")
        raise


if __name__ == "__main__":
    for _ in range(10):
        print(call_model("What are the main features of LangChain?")["answer"])
