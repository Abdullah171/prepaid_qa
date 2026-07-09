"""Command-line interface for the performance planning Q&A pipeline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Sequence

from performance_planning_qa.config import load_settings
from performance_planning_qa.pipeline import NL2SQLPipeline, PipelineResult


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Ask natural-language analytical questions over the performance planning Teradata tables.",
    )
    parser.add_argument(
        "question",
        nargs="*",
        help="Question to answer. If omitted, interactive mode starts.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate and validate SQL without executing it.",
    )
    parser.add_argument(
        "--show-sql",
        action="store_true",
        help="Print generated SQL before the answer.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the full pipeline result as JSON.",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=None,
        help="Path to a .env file. Defaults to the repo .env.",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Force interactive mode even when no question is supplied.",
    )
    parser.add_argument(
        "--no-prompt-log",
        action="store_true",
        help="No-op while prompt logging is disabled.",
    )
    parser.add_argument(
        "--prompt-log-dir",
        type=Path,
        default=None,
        help="No-op unless prompt logging is re-enabled in the pipeline.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    settings = load_settings(args.env_file)
    if args.no_prompt_log or args.prompt_log_dir is not None:
        from dataclasses import replace

        prompt_log = settings.prompt_log
        if args.prompt_log_dir is not None:
            prompt_log = replace(prompt_log, directory=args.prompt_log_dir)
        if args.no_prompt_log:
            prompt_log = replace(prompt_log, enabled=False)
        settings = replace(settings, prompt_log=prompt_log)
    pipeline = NL2SQLPipeline(settings)

    try:
        question = " ".join(args.question).strip()
        if args.interactive or not question:
            return run_interactive(pipeline, args)

        result = pipeline.ask(question, dry_run=args.dry_run)
        print_result(result, show_sql=args.show_sql or args.dry_run, as_json=args.json)
        return 0
    finally:
        pipeline.close()


def run_interactive(pipeline: NL2SQLPipeline, args: argparse.Namespace) -> int:
    print("Performance Planning Q&A. Type 'exit' or 'quit' to stop.")
    while True:
        try:
            question = input("\nQuestion> ").strip()
        except EOFError:
            print()
            return 0
        if question.lower() in {"exit", "quit"}:
            return 0
        if not question:
            continue

        try:
            result = pipeline.ask(question, dry_run=args.dry_run)
            print_result(result, show_sql=args.show_sql or args.dry_run, as_json=args.json)
        except Exception as exc:
            print(f"Error: {exc}", file=sys.stderr)


def print_result(result: PipelineResult, *, show_sql: bool, as_json: bool) -> None:
    if as_json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2, default=str))
        return

    if result.generated_sql.needs_clarification:
        print(result.generated_sql.clarifying_question or "The question needs clarification.")
        print_prompt_logs(result)
        return

    if result.generated_sql.direct_answer:
        print("Answer:")
        print(result.answer or result.generated_sql.direct_answer)
        print_prompt_logs(result)
        return

    if show_sql and result.sql:
        print("SQL:")
        print(result.sql)

    if result.answer:
        print("Answer:")
        print(result.answer)

    if result.query_result:
        print(f"\nRows returned: {result.query_result.row_count}")
        print(f"Query time: {result.query_result.elapsed_ms} ms")

    print_prompt_logs(result)


def print_prompt_logs(result: PipelineResult) -> None:
    # Prompt log printing is disabled for normal runs.
    # if result.prompt_log_paths:
    #     print("\nPrompt logs:")
    #     for path in result.prompt_log_paths:
    #         print(f"- {path}")
    return None


def run() -> None:
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        raise SystemExit(130)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
