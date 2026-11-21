# AutomationBench Public

**600 tasks across six domains · OpenCode 1.19.5 · Vision Large with continual learning**

## Start

1. Install Python 3.9+, Git, and uv. Have Node.js with npm available if OpenCode 1.19.5 is absent.
2. Set `VISPARK_LAB_API` in this repository’s `.env`. Copy `.env.example` if needed.
3. Double-click `Start.command` or run `./start` to run all 600 public tasks. The launcher checks out the pinned Zapier release, installs its locked dependencies, and installs pinned OpenCode locally if needed. Set `BENCH_WORKERS` in `.env` to change default concurrency.

```sh
./start --plan
./start --task sales.multi_hop_lookup
```

OpenCode uses Zapier’s simulated apps through the local tool adapter. Each task starts with a fresh simulated company and fresh Vision memory. The launcher uses local task labels from `tasks.txt`. Zapier's original assertions grade the simulated company's final state.

## Results

Open `results/<run>/summary.json` for strict pass rate, partial credit, and the number of errors. Aborted tasks contribute zero to the reported aggregate. `run.json` records the release, settings, and task IDs. Each task has an individual JSON result with Vision usage.

[Official AutomationBench public set](https://github.com/zapier/AutomationBench)
