import argparse
import json
import os
import subprocess
import sys

from bootstrap import REPO, ensure_env, require_tools, checkout, result_directory
from cl_adapter import load_key, read_env, add_continual_learning_argument, resolve_continual_learning
from opencode_driver import OPENCODE_VERSION, prepare_opencode

URL = "https://github.com/zapier/AutomationBench"
REVISION = "4a8e1061254004d9dac807054eed33fad7d1ff14"


def main():
    settings = read_env(REPO)
    parser = argparse.ArgumentParser(description="AutomationBench public set with OpenCode and Vision")
    parser.add_argument("--workers", type=int, default=settings.get("BENCH_WORKERS") or "1")
    parser.add_argument("--task", action="append")
    parser.add_argument("--plan", action="store_true")
    add_continual_learning_argument(parser)
    args = parser.parse_args()
    try:
        continual_learning = resolve_continual_learning(args.continual_learning, settings)
    except ValueError as error:
        parser.error(str(error))
    official = (REPO / "tasks.txt").read_text().splitlines()
    selected = args.task or official
    if len(set(official)) != 600:
        raise RuntimeError("Expected the 600-task AutomationBench public manifest")
    if args.workers < 1 or len(set(selected)) != len(selected) or not set(selected) <= set(official):
        parser.error("Use positive workers and unique task IDs from tasks.txt")
    if args.plan:
        print(json.dumps({
            "release": "1.0.6", "harness": "OpenCode + Vision", "split": "public",
            "workers": args.workers, "continual_learning": continual_learning, "task_count": len(selected), "tasks": selected,
        }, indent=2))
        return 0
    ensure_env()
    load_key(REPO)
    require_tools("git", "uv")
    source = checkout(URL, REVISION)
    env = os.environ | {
        "PYTHONPATH": str(REPO), "VISION_OPENCODE_BIN": str(prepare_opencode(REPO)),
    }
    command = ["uv", "run", "--locked", "python", str(REPO / "evaluate.py"), "--workers", str(args.workers)]
    output = result_directory(
        benchmark="AutomationBench", harness="OpenCode + Vision",
        release="1.0.6", tasks=selected, workers=args.workers, continual_learning=continual_learning, split="public",
        revision=REVISION, opencode_version=OPENCODE_VERSION, max_steps=50,
    )
    command.extend([
        "--output", str(output),
        "--continual-learning" if continual_learning else "--no-continual-learning",
    ])
    for task in args.task or []:
        command.extend(["--task", task])
    return subprocess.run(command, cwd=source, env=env).returncode


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        print(f"Benchmark startup or run failed: {error}", file=sys.stderr)
        raise SystemExit(1)
