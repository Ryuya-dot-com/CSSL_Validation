#!/usr/bin/env python3
"""
Run switching-recovery simulations for all predefined generative scenarios.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from simulate_switching_recovery import (
    DEFAULT_OUT_DIR,
    SCENARIOS,
    SimulationConfig,
    parse_threshold_grid,
    run_simulation,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--participants", type=int, default=80)
    parser.add_argument("--seed", type=int, default=20260526)
    parser.add_argument("--posterior-threshold", type=float, default=0.70)
    parser.add_argument(
        "--threshold-grid",
        default="0.55,0.60,0.65,0.70,0.75,0.80,0.85,0.90",
    )
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR / "scenario_sweep")
    args = parser.parse_args()
    if args.participants <= 0:
        raise SystemExit("--participants must be positive")
    if not 0 < args.posterior_threshold < 1:
        raise SystemExit("--posterior-threshold must be between 0 and 1")
    return args


def main() -> None:
    args = parse_args()
    threshold_grid = parse_threshold_grid(args.threshold_grid, args.posterior_threshold)
    for scenario_name, profile in SCENARIOS.items():
        scenario_out_dir = args.out_dir / scenario_name
        config = SimulationConfig(
            participants=args.participants,
            seed=args.seed,
            posterior_threshold=args.posterior_threshold,
            threshold_grid=threshold_grid,
            profile=profile,
            out_dir=scenario_out_dir,
        )
        run_simulation(config)
        print(f"{scenario_name}: {scenario_out_dir}")


if __name__ == "__main__":
    main()
