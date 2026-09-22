import argparse
import asyncio
import csv
import importlib.util
import time
from typing import Callable

import yaml
from langsmith import Client

from langfuzz.redteam import _show_results, create_judge_graph


def parse_rows(value: str) -> set[int]:
    rows = set()
    for part in value.split(","):
        bounds = part.strip().split("-", 1)
        try:
            start = int(bounds[0])
            end = int(bounds[-1])
        except ValueError as error:
            raise argparse.ArgumentTypeError("rows must look like 1,3-5") from error
        if start < 1 or end < start:
            raise argparse.ArgumentTypeError(
                "row numbers must be positive ascending ranges"
            )
        rows.update(range(start, end + 1))
    return rows


def load_pairs(
    csv_path: str,
    selected_rows: set[int] | None = None,
    rerun: bool = False,
) -> list[dict[str, str]]:
    with open(csv_path, newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        fields = set(reader.fieldnames or [])
        if {"question_1", "question_2"} <= fields:
            columns = ("question_1", "question_2")
        elif {"input_1", "input_2"} <= fields:
            columns = ("input_1", "input_2")
        else:
            raise ValueError(
                "CSV must contain question_1 and question_2 columns "
                "(input_1 and input_2 are also supported)"
            )
        pairs = []
        for pair_number, row in enumerate(reader, start=1):
            if selected_rows is not None and pair_number not in selected_rows:
                continue
            has_answer = (row.get("answer") or "").strip() or all(
                (row.get(column) or "").strip()
                for column in ("answer_1", "answer_2")
            )
            if not rerun and has_answer:
                continue
            input_1 = row[columns[0]].strip()
            input_2 = row[columns[1]].strip()
            if not input_1 or not input_2:
                raise ValueError(f"CSV row {pair_number + 1} contains an empty question")
            pairs.append({"input_1": input_1, "input_2": input_2})
    return pairs


def load_call_model(file_path: str) -> Callable:
    spec = importlib.util.spec_from_file_location("call_model_module", file_path)
    if spec is None or spec.loader is None:
        raise ValueError(f"Could not load model file: {file_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.call_model


async def score_pairs(
    pairs: list[dict[str, str]],
    call_model: Callable,
    config: dict,
    max_concurrency: int,
) -> list[dict]:
    graph = create_judge_graph(call_model)
    semaphore = asyncio.Semaphore(max_concurrency)

    async def score(pair):
        async with semaphore:
            return await graph.ainvoke(pair, {"configurable": config})

    tasks = [asyncio.create_task(score(pair)) for pair in pairs]
    results = []
    for task in asyncio.as_completed(tasks):
        results.append(await task)
        print(f"Scored {len(results)}/{len(tasks)} pairs")
    return sorted(results, key=lambda result: result["judge"]["similarity"])


async def run(
    config: dict,
    csv_path: str,
    dataset_id: str | None,
    max_concurrency: int | None,
    max_similarity: int | None,
    selected_rows: set[int] | None,
    non_interactive: bool,
    rerun: bool,
):
    pairs = load_pairs(csv_path, selected_rows, rerun)
    if not pairs:
        print("No unanswered rows to run")
        return
    max_concurrency = max_concurrency or config.get("max_concurrency", 10)
    max_similarity = max_similarity or config.get("max_similarity", 10)
    call_model = load_call_model(config["model_file"])
    results = await score_pairs(pairs, call_model, config, max_concurrency)

    client = Client()
    dataset_id = dataset_id or config.get("dataset_id")
    if dataset_id is None:
        name = f"Redteaming results {time.strftime('%Y-%m-%d %H:%M:%S')}"
        dataset_id = client.create_dataset(dataset_name=name).id
        print(f"Created dataset: {name}")

    for result in results:
        if result["judge"]["similarity"] > max_similarity:
            continue
        if non_interactive:
            client.create_example(
                inputs={
                    "question_1": result["input_1"],
                    "question_2": result["input_2"],
                },
                outputs={
                    "answer_1": result["output_1"],
                    "answer_2": result["output_2"],
                    "similarity": result["judge"]["similarity"],
                    "logic": result["judge"]["logic"],
                },
                dataset_id=dataset_id,
            )
            continue
        await _show_results(result)
        choice = input()
        if choice == "1":
            inputs = [{"question": result["input_1"]}]
        elif choice == "2":
            inputs = [{"question": result["input_2"]}]
        elif choice == "3":
            continue
        elif choice == "q":
            break
        else:
            inputs = [
                {"question": result["input_1"]},
                {"question": result["input_2"]},
            ]
        client.create_examples(inputs=inputs, dataset_id=dataset_id)


def main():
    parser = argparse.ArgumentParser(
        description="Score question pairs from a CSV and curate them into LangSmith"
    )
    parser.add_argument("config_path", help="Path to the configuration file")
    parser.add_argument("csv_path", help="Path to the question-pairs CSV")
    parser.add_argument("--dataset_id", help="ID of the dataset to use")
    parser.add_argument("--max_concurrency", type=int)
    parser.add_argument("--max_similarity", type=int)
    parser.add_argument(
        "--rows",
        type=parse_rows,
        help="1-based data rows to run, for example 1,3-5",
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Add scored pairs directly to the dataset without prompting",
    )
    parser.add_argument(
        "--rerun",
        action="store_true",
        help="Run all rows, including rows that already have answers",
    )
    args = parser.parse_args()

    with open(args.config_path) as file:
        config = yaml.safe_load(file)
    asyncio.run(
        run(
            config,
            args.csv_path,
            args.dataset_id,
            args.max_concurrency,
            args.max_similarity,
            args.rows,
            args.non_interactive,
            args.rerun,
        )
    )
