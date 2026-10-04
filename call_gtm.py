import argparse
import json
import os
import re
from copy import deepcopy

from langgraph_sdk import get_sync_client

URL = "https://gtm-agent-b8803b32b08057d4968c5f671d7e0149.us.langgraph.app"


def get_client():
    return get_sync_client(
        url=URL, api_key=os.environ["LANGSMITH_API_KEY"], timeout=600
    )


def build_config(run_config: dict | None = None) -> dict:
    config = deepcopy(run_config or {})
    configurable = {
        "user_id": os.environ.get("GTM_USER_ID", "U_LOCAL_LANGFUZZ"),
        "trigger": "CHAT",
        "run_surface": "DASHBOARD",
        "interactive_profile": "GTM_PLATFORM_WEB",
        "presentation_capabilities": ["MARKDOWN"],
        **config.get("configurable", {}),
        "__engine_validation_replay__": True,
    }
    if not isinstance(configurable["user_id"], str) or not re.fullmatch(
        r"[UW][A-Z0-9_]+", configurable["user_id"]
    ):
        raise ValueError(
            "GTM_USER_ID must be a Slack member ID, not a LangSmith user UUID"
        )
    config["configurable"] = configurable
    return config


def call_model(question: str, run_config: dict | None = None) -> dict[str, str]:
    config = build_config(run_config)
    client = get_client()
    thread = client.threads.create()
    config["configurable"]["thread_id"] = thread["thread_id"]
    run_id = None

    def capture_run(metadata):
        nonlocal run_id
        run_id = metadata["run_id"]

    result = client.runs.wait(
        thread["thread_id"],
        "main",
        input={"messages": [{"role": "user", "content": question}]},
        config=config,
        on_run_created=capture_run,
    )
    if result.get("__interrupt__"):
        raise RuntimeError(f"GTM run interrupted; run_id={run_id}")
    messages = result.get("messages", [])
    if not messages or messages[-1].get("type", messages[-1].get("role")) not in (
        "ai",
        "assistant",
    ):
        raise RuntimeError(f"GTM returned no final assistant answer; run_id={run_id}")
    message = messages[-1]
    if message.get("tool_calls"):
        raise RuntimeError(f"GTM ended on a tool call; run_id={run_id}")
    content = message["content"]
    if isinstance(content, list):
        content = "\n".join(
            block["text"] for block in content if block.get("type") == "text"
        )
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError(f"GTM returned an empty answer; run_id={run_id}")
    return {"answer": content, "trace_id": run_id}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("question")
    args = parser.parse_args()
    print(json.dumps({"input": args.question, **call_model(args.question)}, indent=2))
