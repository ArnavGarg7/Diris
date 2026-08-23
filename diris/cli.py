"""Command-line interface.

    python -m diris ingest data/documents            # ingest a file or folder
    python -m diris ask "Who is Harry Potter?"        # one-shot question
    python -m diris chat                               # interactive, with memory
    python -m diris stats                              # knowledge base summary
"""
from __future__ import annotations

import argparse
import sys

from .pipeline import Pipeline


def _print_answer(ans) -> None:
    print("\n" + ans.answer.strip())
    bar = "#" * int(round(ans.confidence * 10))
    print(f"\nconfidence: {ans.confidence:.2f} [{bar:<10}]")
    if ans.reasoning_path:
        print(f"reasoning : {ans.reasoning_path}")
    if ans.conflicts:
        print(f"conflicts : {ans.conflicts}")
    if ans.citations:
        srcs = [f"{c}={ans.sources.get(c, {}).get('doc', '?')}" for c in ans.citations]
        print("sources   : " + ", ".join(srcs))


def cmd_ingest(args) -> None:
    p = Pipeline()
    totals = p.ingest_path(args.path)
    print(f"\nDone. {totals}")
    print(f"Knowledge base now: {p.stats()}")


def cmd_ask(args) -> None:
    p = Pipeline()
    if not p.vs.chunks:
        print("Knowledge base is empty. Run `ingest` first.")
        sys.exit(1)
    _print_answer(p.query(args.question))


def cmd_chat(args) -> None:
    p = Pipeline()
    if not p.vs.chunks:
        print("Knowledge base is empty. Run `ingest` first.")
        sys.exit(1)
    print("Interactive chat (FR-11 conversation memory). Type 'exit' to quit.\n")
    history: list[dict] = []
    while True:
        try:
            q = input("you > ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if q.lower() in {"exit", "quit"}:
            break
        if not q:
            continue
        ans = p.query(q, history=history)
        _print_answer(ans)
        history.append({"role": "user", "content": q})
        history.append({"role": "assistant", "content": ans.answer})
        print()


def cmd_stats(args) -> None:
    print(Pipeline().stats())


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="diris", description="Data Injection and Retrieval System")
    sub = parser.add_subparsers(dest="command", required=True)

    p_ing = sub.add_parser("ingest", help="ingest a file or folder")
    p_ing.add_argument("path")
    p_ing.set_defaults(func=cmd_ingest)

    p_ask = sub.add_parser("ask", help="ask a one-shot question")
    p_ask.add_argument("question")
    p_ask.set_defaults(func=cmd_ask)

    p_chat = sub.add_parser("chat", help="interactive chat with memory")
    p_chat.set_defaults(func=cmd_chat)

    p_stats = sub.add_parser("stats", help="show knowledge base stats")
    p_stats.set_defaults(func=cmd_stats)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
