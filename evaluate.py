import argparse
import asyncio
import hashlib
import json
import sys
import subprocess
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from automationbench.domains import PUBLIC_DOMAINS, get_combined_dataset
from automationbench.rubric import create_rubric, partial_credit, task_completed_correctly
from automationbench.runner import AutomationBenchEnv
from automationbench.scripts.eval import _task_name
from automationbench.tools.api import api_fetch, api_search, base64_encode

from bootstrap import REPO
from cl_adapter import add_continual_learning_argument, bridge, load_key, read_env, resolve_continual_learning
from opencode_driver import OpenCode

SYSTEM = (
    "Complete the user's business workflow by using the simulated app tools. "
    "Discover APIs with api_search and carry out changes with api_fetch. "
    "Only the simulated company's final state is graded. Work without asking the user. "
    "When finished, briefly report the actions you took."
)


def run_attempt(row, task, env, key, output, *, continual_learning):
    state = asyncio.run(env.setup_state(dict(row)))
    world = state["world"]
    lock = threading.Lock()

    def rpc(call):
        tools = {"api_fetch": lambda **args: api_fetch(world=world, **args),
                 "api_search": api_search, "base64_encode": base64_encode}
        with lock:
            try:
                text = tools[call["name"]](**call.get("arguments", {}))
                return {"content": [{"type": "text", "text": str(text)}]}
            except (KeyError, TypeError, ValueError):
                return {"isError": True, "content": [{"type": "text", "text": "Invalid simulator tool arguments"}]}

    with bridge(key, limit=50, rpc=rpc, continual_learning=continual_learning) as (url, token, vision):
        with tempfile.TemporaryDirectory(prefix="vision-automation-") as profile:
            open_code = OpenCode(Path(profile), url, token, [
                sys.executable, str(REPO / "mcp_tools.py"), url.removesuffix("/v1") + "/tools", token,
            ])
            prompt = json.dumps(row["prompt"], ensure_ascii=False, default=str)
            try:
                answer = open_code.prompt(SYSTEM + "\n\nBenchmark prompt:\n" + prompt, timeout=7200)
                partial = partial_credit(state)
                record = {"task": task, "partial_credit": partial,
                          "task_completed_correctly": task_completed_correctly(state), "answer": answer}
            except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
                record = {"task": task, "error": str(error)}
            record["usage"] = vision.report()
    safe_name = task.replace("/", "_")
    (output / (safe_name + ".json")).write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
    print(task, "error" if "error" in record else record["task_completed_correctly"], flush=True)
    return record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--task", action="append")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--plan", action="store_true")
    add_continual_learning_argument(parser)
    args = parser.parse_args()
    try:
        continual_learning = resolve_continual_learning(args.continual_learning, read_env(REPO))
    except ValueError as error:
        parser.error(str(error))
    dataset = get_combined_dataset(PUBLIC_DOMAINS)
    if len(dataset) != 600:
        raise RuntimeError(f"Expected 600 tasks, found {len(dataset)}")
    official_names = "".join(_task_name(row) + "\n" for row in dataset)
    if hashlib.sha256(official_names.encode()).hexdigest() != "805c20fdc66b37fcdec15cba0039d7439e2988be0102c1a20f82a0e5b78a2637":
        raise RuntimeError("The released dataset does not match the pinned task order")
    names = (REPO / "tasks.txt").read_text().splitlines()
    if args.task and not set(args.task) <= set(names):
        parser.error("Provide task IDs from the public manifest")
    indices = [index for index, name in enumerate(names) if not args.task or name in args.task]
    selected_names = [names[index] for index in indices]
    dataset = dataset.select(indices)
    if args.plan:
        print(json.dumps({"task_count": len(dataset), "continual_learning": continual_learning, "tasks": selected_names}, indent=2))
        return 0
    if args.workers < 1 or args.output is None:
        parser.error("Provide positive workers and an output directory")
    key = load_key(REPO)
    env = AutomationBenchEnv(dataset=dataset, rubric=create_rubric(), max_turns=50, toolset="api")
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        records = list(executor.map(
            lambda row, task: run_attempt(row, task, env, key, args.output, continual_learning=continual_learning),
            dataset, selected_names,
        ))
    complete = [record for record in records if "error" not in record]
    summary = {
        "planned": len(records), "graded": len(complete), "errors": len(records) - len(complete),
        "strict_pass_rate": sum(row["task_completed_correctly"] for row in complete) / len(records),
        "mean_partial_credit": sum(row["partial_credit"] for row in complete) / len(records),
    }
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return int(len(complete) != len(records))


if __name__ == "__main__":
    raise SystemExit(main())
