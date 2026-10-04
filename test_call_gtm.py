import unittest
from unittest.mock import patch

from call_gtm import build_config, call_model


class GTMConnectorTests(unittest.TestCase):
    def test_replay_is_forced_without_mutating_existing_config(self):
        original = {
            "configurable": {
                "__engine_validation_replay__": False,
                "account_id": "account",
            },
            "tags": ["smoke"],
        }
        config = build_config(original)
        self.assertIs(config["configurable"]["__engine_validation_replay__"], True)
        self.assertEqual(config["configurable"]["account_id"], "account")
        self.assertEqual(config["tags"], ["smoke"])
        self.assertIs(original["configurable"]["__engine_validation_replay__"], False)

    @patch("call_gtm.get_client")
    def test_request_and_text_blocks(self, get_client):
        client = get_client.return_value
        client.threads.create.return_value = {"thread_id": "thread"}

        def wait(*args, **kwargs):
            kwargs["on_run_created"]({"run_id": "run"})
            return {
                "messages": [
                    {
                        "type": "ai",
                        "content": [
                            {"type": "thinking", "thinking": "hidden"},
                            {"type": "text", "text": "First"},
                            {"type": "text", "text": "Second"},
                        ],
                    }
                ]
            }

        client.runs.wait.side_effect = wait
        self.assertEqual(
            call_model("Question"), {"answer": "First\nSecond", "trace_id": "run"}
        )
        args, kwargs = client.runs.wait.call_args
        self.assertEqual(args, ("thread", "main"))
        self.assertEqual(
            kwargs["input"], {"messages": [{"role": "user", "content": "Question"}]}
        )
        self.assertIs(
            kwargs["config"]["configurable"]["__engine_validation_replay__"], True
        )
        self.assertEqual(kwargs["config"]["configurable"]["thread_id"], "thread")

    @patch("call_gtm.get_client")
    def test_tool_output_is_not_reported_as_an_answer(self, get_client):
        client = get_client.return_value
        client.threads.create.return_value = {"thread_id": "thread"}
        for result in (
            {"__interrupt__": [{"value": "consent"}]},
            {"messages": [{"type": "tool", "content": "result"}]},
            {
                "messages": [
                    {"type": "ai", "content": "", "tool_calls": [{"name": "read_file"}]}
                ]
            },
            {"messages": [{"type": "ai", "content": []}]},
        ):
            with self.subTest(result=result):
                client.runs.wait.return_value = result
                with self.assertRaises(RuntimeError):
                    call_model("Question")


if __name__ == "__main__":
    unittest.main()
