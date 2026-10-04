import argparse
import asyncio
import csv
import inspect
import os
from typing import Any, Callable

import yaml

from langfuzz.csv_runner import load_call_model
from langfuzz.redteam import _normalize_model_result

RESULT_FIELDS = [
    "trace_id_1",
    "trace_id_2",
    "question_1",
    "question_2",
    "claim_from_answer_1",
    "expected_answer_2",
    "correct_answer",
    "answer_1",
    "answer_2",
    "authoritative_evidence",
    "reasoning",
    "outcome",
]
REVIEW_FIELDS = [
    "claim_from_answer_1",
    "expected_answer_2",
    "correct_answer",
    "authoritative_evidence",
    "reasoning",
    "outcome",
]


def read_rows(path: str) -> list[dict[str, str]]:
    with open(path, newline="", encoding="utf-8-sig") as file:
        return list(csv.DictReader(file))


def index_rows(rows: list[dict[str, str]], source: str) -> dict[str, dict[str, str]]:
    indexed = {}
    for row_number, row in enumerate(rows, start=2):
        row_id = row.get("id", "").strip()
        if not row_id:
            raise ValueError(f"{source} row {row_number} has no id")
        if row_id in indexed:
            raise ValueError(f"{source} contains duplicate id {row_id!r}")
        indexed[row_id] = row
    return indexed


async def ask_questions(
    call_model: Callable, rows: list[dict[str, str]], max_concurrency: int
) -> list[dict[str, Any]]:
    semaphore = asyncio.Semaphore(max_concurrency)

    async def ask(row_number: int, row: dict[str, str]) -> dict[str, Any]:
        question = row.get("question", "").strip()
        if not question:
            raise ValueError(f"questions row {row_number} has no question")
        async with semaphore:
            if inspect.iscoroutinefunction(call_model):
                result = await call_model(question)
            else:
                result = await asyncio.to_thread(call_model, question)
        answer, trace_id = _normalize_model_result(result)
        return {
            "id": row.get("id", "").strip() or str(row_number - 1),
            "question": question,
            "answer": answer,
            "trace_id": trace_id,
        }

    return await asyncio.gather(
        *(ask(row_number, row) for row_number, row in enumerate(rows, start=2))
    )


def write_ask_results(path: str, rows: list[dict[str, Any]]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=["id", "question", "answer", "trace_id"])
        writer.writeheader()
        writer.writerows(rows)


def append_records(
    initial_path: str,
    derived_path: str,
    reviews_path: str,
    output_path: str,
) -> None:
    initial = index_rows(read_rows(initial_path), initial_path)
    derived = index_rows(read_rows(derived_path), derived_path)
    reviews = index_rows(read_rows(reviews_path), reviews_path)
    if initial.keys() != derived.keys() or initial.keys() != reviews.keys():
        raise ValueError("initial, derived, and review files must contain the same ids")

    output_exists = os.path.exists(output_path) and os.path.getsize(output_path) > 0
    with open(output_path, "a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=RESULT_FIELDS)
        if not output_exists:
            writer.writeheader()
        for row_id, first in initial.items():
            second = derived[row_id]
            review = reviews[row_id]
            missing = [field for field in REVIEW_FIELDS if not review.get(field, "").strip()]
            if missing:
                raise ValueError(
                    f"{reviews_path} id {row_id!r} is missing {', '.join(missing)}"
                )
            writer.writerow(
                {
                    "trace_id_1": first.get("trace_id", ""),
                    "trace_id_2": second.get("trace_id", ""),
                    "question_1": first.get("question", ""),
                    "question_2": second.get("question", ""),
                    "answer_1": first.get("answer", ""),
                    "answer_2": second.get("answer", ""),
                    **{field: review[field] for field in REVIEW_FIELDS},
                }
            )


def ask_command(args: argparse.Namespace) -> None:
    with open(args.config_path, encoding="utf-8") as file:
        config = yaml.safe_load(file)
    model_file = config["model_file"]
    if not os.path.isabs(model_file):
        model_file = os.path.join(os.path.dirname(os.path.abspath(args.config_path)), model_file)
    call_model = load_call_model(model_file)
    rows = read_rows(args.questions_path)
    results = asyncio.run(ask_questions(call_model, rows, args.max_concurrency))
    write_ask_results(args.output_path, results)
    print(f"Wrote {len(results)} responses to {args.output_path}")


def record_command(args: argparse.Namespace) -> None:
    append_records(
        args.initial_path,
        args.derived_path,
        args.reviews_path,
        args.output_path,
    )
    print(f"Appended reviewed attempts to {args.output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run and record two-stage claim-derived counter-fuzz probes"
    )
    subparsers = parser.add_subparsers(required=True)

    ask_parser = subparsers.add_parser("ask", help="Run independent target questions")
    ask_parser.add_argument("config_path")
    ask_parser.add_argument("questions_path", help="CSV with id and question columns")
    ask_parser.add_argument("output_path")
    ask_parser.add_argument("--max-concurrency", type=int, default=5)
    ask_parser.set_defaults(func=ask_command)

    record_parser = subparsers.add_parser(
        "record", help="Merge two ask outputs and reviewed metadata into a results CSV"
    )
    record_parser.add_argument("initial_path")
    record_parser.add_argument("derived_path")
    record_parser.add_argument("reviews_path")
    record_parser.add_argument("output_path")
    record_parser.set_defaults(func=record_command)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
