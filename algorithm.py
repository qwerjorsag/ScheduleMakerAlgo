"""Standalone timetable optimizer. School data lives in School parametrs/*.json."""
from pathlib import Path
import argparse

from timetable.models import UniversityDataset
from timetable.solver import SolveOptions, solve_timetable


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--time-limit", type=int, default=300, help="Solver limit in seconds.")
    args = parser.parse_args()
    data_dir = Path(__file__).resolve().parent / "School parametrs"
    dataset = UniversityDataset.load_split(data_dir)
    result = solve_timetable(dataset, SolveOptions(time_limit_seconds=args.time_limit))
    output = Path(__file__).resolve().parent / "schedule.json"
    result.save(output)
    print(f"Solved ({result.status}); {len(result.sessions)} sessions saved to {output}")


if __name__ == "__main__":
    main()
