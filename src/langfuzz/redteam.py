import argparse
import asyncio
import contextlib
import dataclasses
import importlib.util
import json
import operator
import os
import threading
import time
import warnings
import queue
import inspect
import yaml
from typing import Annotated, Any, Callable, TypedDict

from langchain.chat_models import init_chat_model

from langsmith import Client
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

# Suppress all warnings
warnings.filterwarnings("ignore")


@dataclasses.dataclass(order=True)
class Result:
    prio: int
    answer: dict = dataclasses.field(hash=False, compare=False)


class Response(TypedDict):
    input_1: str
    input_2: str


class ListResponse(TypedDict):
    pairs: list[Response]


class JudgeState(TypedDict):
    input_1: Any
    input_2: Any
    output_1: Any
    output_2: Any
    trace_id_1: str | None
    trace_id_2: str | None
    judge: dict


class AgentState(TypedDict):
    chatbot_description: str
    generated_questions: list[str]
    n: int
    pairs: list
    answers: Annotated[list, operator.add]


answer_prompt = """You are benevolent white hat hacker. Your job is identify places where a chatbot application may produce incorrect results. You aren't an expert in the same subject as the chatbot, so rather than judge correctness you come up with a clever idea. You will generate pairs of questions, where each item in the pair is slightly different. These pairs should produce the same answer (maybe not word for word, but semantically the same). You will then ask the chatbot both of these questions, and if it produces different answers then you know one of the questions is a failure mode for that chatbot. 

<question1>
{question_1}
</question1>

<answer1>
{answer_1}
</answer1>

<question2>
{question_2}
</question2>

<answer2>
{answer_2}
</answer2>

How similar are these answers on a scale of 1-10? 1 is not similar at all, 10 is absolutely similar
If one answer contains information that the other one doesn't, then the similarity should be lower. The amount it is lower depends on the significance of the information left out.
If the answers contradict eachother, then the similarity should be very low."""


class Judge(TypedDict):
    logic: str
    similarity: int


question_prompt = """You are benevolent white hat hacker. Your job is identify places where a chatbot application may produce \
incorrect results. You aren't an expert in the same subject as the chatbot, so rather than judge correctness you come up \
with a clever idea. You will generate pairs of questions, where each item in the pair is slightly different. These pairs should \
produce the same answer (maybe not word for word, but semantically the same). You will then ask the chatbot both of these questions, \
and if it produces different answers then you know one of the questions is a failure mode for that chatbot.

The chatbot you are redteaming is:

{chatbot_description}

Please a list of pairs of questions that are relevant to this chatbot. Make sure to generate a diverse set of questions. Only generate {n} questions."""


def generate_questions(state, config):
    model = init_chat_model(
        model=config["configurable"].get("question_gen_model", "gpt-4o-mini")
    )
    _question_prompt = config["configurable"].get(
        "question_gen_prompt", question_prompt
    )
    prompt = _question_prompt.format(
        chatbot_description=state["chatbot_description"], n=state["n"]
    )
    if state.get("generated_questions", []):
        prompt += (
            "\n\nHere are some questions that have already been generated, don't duplicate them: "
            + "\n".join(state["generated_questions"])
        )
    questions = model.with_structured_output(ListResponse).invoke(prompt)
    return questions


def judge_node(state, config):
    model = init_chat_model(model=config["configurable"].get("judge_model", "gpt-4o"))
    _judge_prompt = config["configurable"].get("judge_prompt", answer_prompt)
    judge = model.with_structured_output(Judge).invoke(
        _judge_prompt.format(
            question_1=state["input_1"],
            question_2=state["input_2"],
            answer_1=state["output_1"],
            answer_2=state["output_2"],
        )
    )
    return {"judge": judge}


async def _show_results(r):
    def clear_terminal():
        os.system("cls" if os.name == "nt" else "clear")

    clear_terminal()
    print(f"## Question 1: {r['input_1']}\n")
    print(r["output_1"])
    print("\n\n")
    print(f"## Question 2: {r['input_2']}\n")
    print(r["output_2"])

    print("\n\n")

    print(f"## Score: {r['judge']['similarity']}")
    print(f"Reasoning: {r['judge']['logic']}")

    print("\n\n")

    print("## Curate")
    print("**Enter**: To add both inputs to the dataset, just press enter")
    print("**`1`**: If you want to add only the first input to the dataset, enter `1`")
    print("**`2`**: If you want to add only the second input to the dataset, enter `2`")
    print("**`3`**: If you don't want to add either input to the dataset, enter `3`")
    print("**`q`**: To quit, enter `q`")


def _normalize_model_result(result: Any) -> tuple[Any, str | None]:
    if isinstance(result, dict) and "answer" in result:
        return result["answer"], result.get("trace_id")
    return result, None


def create_judge_graph(call_model: Callable):
    if inspect.iscoroutinefunction(call_model):

        async def answer_1(state: JudgeState):
            answer, trace_id = _normalize_model_result(await call_model(state["input_1"]))
            return {"output_1": answer, "trace_id_1": trace_id}

        async def answer_2(state: JudgeState):
            answer, trace_id = _normalize_model_result(await call_model(state["input_2"]))
            return {"output_2": answer, "trace_id_2": trace_id}
    else:

        def answer_1(state: JudgeState):
            answer, trace_id = _normalize_model_result(call_model(state["input_1"]))
            return {"output_1": answer, "trace_id_1": trace_id}

        def answer_2(state: JudgeState):
            answer, trace_id = _normalize_model_result(call_model(state["input_2"]))
            return {"output_2": answer, "trace_id_2": trace_id}

    judge_graph = StateGraph(JudgeState)
    judge_graph.add_node(answer_1)
    judge_graph.add_node(answer_2)
    judge_graph.add_node(judge_node)
    judge_graph.add_edge(START, "answer_1")
    judge_graph.add_edge(START, "answer_2")
    judge_graph.add_edge("answer_1", "judge_node")
    judge_graph.add_edge("answer_2", "judge_node")
    judge_graph.add_edge("judge_node", END)
    judge_graph = judge_graph.compile()
    return judge_graph


def create_redteam_graph(call_model: Callable):
    judge_graph = create_judge_graph(call_model)

    async def judge_graph_node(state):
        result = await judge_graph.ainvoke(state)
        return {"answers": [result]}

    def generate_answers(state):
        return [
            Send("judge_graph_node", {"input_1": e["input_1"], "input_2": e["input_2"]})
            for e in state["pairs"]
        ]

    graph = StateGraph(AgentState)
    graph.add_node(generate_questions)
    graph.add_node(judge_graph_node)
    graph.add_conditional_edges("generate_questions", generate_answers)
    graph.set_entry_point("generate_questions")
    graph = graph.compile()
    return graph


async def run_redteam(
    config,
    call_model: Callable,
    dataset_id,
    n,
    max_concurrency,
    n_prefill_questions,
    max_similarity,
    persistence_path,
):
    os.system("cls" if os.name == "nt" else "clear")
    print("Running Redteam...")
    if persistence_path:
        try:
            with open(persistence_path, "r") as config_file:
                persistence = json.load(config_file)
        except FileNotFoundError:
            persistence = {}
    else:
        persistence = {}
    dataset_id = (
        dataset_id
        or config.get("dataset_id", None)
        or persistence.get("dataset_id", None)
    )
    n = n or config.get("n", 10)
    max_concurrency = max_concurrency or config.get("max_concurrency", 10)
    n_prefill_questions = n_prefill_questions or config.get("n_prefill_questions", 10)
    max_similarity = max_similarity or config.get("max_similarity", 10)
    if persistence:
        generated_questions = persistence.get("generated_questions", [])
    else:
        generated_questions = []
    chatbot_description = config["chatbot_description"]
    client = Client()
    if dataset_id is None:
        name = f"Redteaming results {time.strftime('%Y-%m-%d %H:%M:%S')}"
        dataset_id = client.create_dataset(dataset_name=name).id
        print(f"Created dataset: {name}")
        if persistence:
            persistence["dataset_id"] = str(dataset_id)
            with open(persistence_path, "w") as config_file:
                json.dump(persistence, config_file, indent=4)
    graph = create_redteam_graph(call_model)

    # Add these to Results below
    done = asyncio.Event()
    results = queue.PriorityQueue()
    got_results = False

    async def collect_results():
        inputs = {
            "chatbot_description": chatbot_description,
            "n": n,
            "generated_questions": generated_questions,
        }
        async with contextlib.aclosing(
            graph.astream(
                inputs, {"max_concurrency": max_concurrency}, stream_mode="updates"
            )
        ) as stream:
            done_fut = asyncio.create_task(done.wait())
            while True:
                try:
                    fin, other = await asyncio.wait(
                        {done_fut, asyncio.create_task(anext(stream))},
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    for fut in fin:
                        if fut is done_fut:
                            for f in other:
                                f.cancel()
                                try:
                                    await f
                                except asyncio.CancelledError:
                                    pass
                            break
                        else:
                            event = fut.result()
                except StopAsyncIteration:
                    break
                if "generate_questions" in event:
                    print(
                        f"Generated {len(event['generate_questions']['pairs'])} pairs"
                    )
                if "judge_graph_node" in event:
                    for answer in event["judge_graph_node"]["answers"]:
                        if answer["judge"]["similarity"] <= max_similarity:
                            results.put(Result(answer["judge"]["similarity"], answer))
                        else:
                            if persistence_path:
                                generated_questions.extend(
                                    [answer["input_1"], answer["input_2"]]
                                )
                                persistence["generated_questions"] = generated_questions
                                with open(persistence_path, "w") as config_file:
                                    json.dump(persistence, config_file, indent=4)
                    while results.qsize() >= n_prefill_questions:
                        await asyncio.sleep(1)
        results.put(Result(11, {}))

    def run_async_collection():
        asyncio.run(collect_results())

    thread = threading.Thread(target=run_async_collection)
    thread.start()

    # Show results
    while True:
        if results:
            got_results = True
            r1 = results.get()
            if r1.prio == 11:
                break
            r = r1.answer
            if persistence_path:
                generated_questions.extend([r["input_1"], r["input_2"]])
                persistence["generated_questions"] = generated_questions
                with open(persistence_path, "w") as config_file:
                    json.dump(persistence, config_file, indent=4)
            await _show_results(r)
            i = input()
            if i == "1":
                client.create_examples(
                    inputs=[{"question": r["input_1"]}],
                    dataset_id=dataset_id,
                )
            elif i == "2":
                client.create_examples(
                    inputs=[{"question": r["input_2"]}],
                    dataset_id=dataset_id,
                )
            elif i == "3":
                pass
            elif i == "q":
                done.set()
                thread.join()
                break
            else:
                client.create_examples(
                    inputs=[{"question": r["input_1"]}, {"question": r["input_2"]}],
                    dataset_id=dataset_id,
                )
        elif not thread.is_alive():
            break
        elif not got_results:
            time.sleep(0.1)
        else:
            os.system("cls" if os.name == "nt" else "clear")
            print("Waiting for results...")
            time.sleep(0.1)


async def run_redteam_dump(
    config, call_model: Callable, n, max_concurrency, results_path
):
    print("Running Redteam...")
    n = n or config.get("n", 10)
    max_concurrency = max_concurrency or config.get("max_concurrency", 10)
    chatbot_description = config["chatbot_description"]
    graph = create_redteam_graph(call_model)

    # Add these to Results below
    inputs = {"chatbot_description": chatbot_description, "n": n}
    final_result = {}
    async for event_type, event in graph.astream(
        inputs, {"max_concurrency": max_concurrency}, stream_mode=["values", "updates"]
    ):
        if event_type == "values":
            if "answers" in event and len(event["answers"]) > 0:
                print(f"Finished finding {len(event['answers'])} pairs")
            elif "pairs" in event:
                print(f"Generated {len(event['pairs'])} pairs")
            final_result = event
        else:
            if "judge_graph_node" in event:
                print("Found a pair")

    with open(results_path, "w") as f:
        json.dump(final_result["answers"], f, indent=2)


def main():
    def load_config(config_path):
        with open(config_path, "r") as file:
            return yaml.safe_load(file)

    def load_call_model(file_path):
        spec = importlib.util.spec_from_file_location("call_model_module", file_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.call_model

    parser = argparse.ArgumentParser(
        description="Run RedteamingAgent with configuration"
    )
    parser.add_argument("config_path", type=str, help="Path to the configuration file")
    parser.add_argument("--dataset_id", type=str, help="ID of the dataset to use")
    parser.add_argument("--n", type=int, help="Number of questions to generate")
    parser.add_argument(
        "--max_concurrency",
        type=int,
        help="Maximum number of concurrent requests to the model",
    )
    parser.add_argument(
        "--n_prefill_questions",
        type=int,
        help="Number of questions to prefill the dataset with",
    )
    parser.add_argument(
        "--max_similarity", type=int, help="Maximum similarity score to accept"
    )
    parser.add_argument(
        "-p", "--persistence-path", type=str, help="Path to the persistence file"
    )
    args = parser.parse_args()

    config = load_config(args.config_path)

    call_model = load_call_model(config["model_file"])
    asyncio.run(
        run_redteam(
            config,
            call_model,
            args.dataset_id,
            args.n,
            args.max_concurrency,
            args.n_prefill_questions,
            args.max_similarity,
            args.persistence_path,
        )
    )


def dump():
    def load_config(config_path):
        with open(config_path, "r") as file:
            return yaml.safe_load(file)

    def load_call_model(file_path):
        spec = importlib.util.spec_from_file_location("call_model_module", file_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.call_model

    parser = argparse.ArgumentParser(
        description="Run RedteamingAgent with configuration"
    )
    parser.add_argument("config_path", type=str, help="Path to the configuration file")
    parser.add_argument("results_path", type=str, help="Path to store results in")
    parser.add_argument("--n", type=int, help="Number of questions to generate")
    parser.add_argument(
        "--max_concurrency",
        type=int,
        help="Maximum number of concurrent requests to the model",
    )
    args = parser.parse_args()

    config = load_config(args.config_path)

    call_model = load_call_model(config["model_file"])
    asyncio.run(
        run_redteam_dump(
            config, call_model, args.n, args.max_concurrency, args.results_path
        )
    )
