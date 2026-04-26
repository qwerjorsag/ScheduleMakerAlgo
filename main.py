from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import sys

from timetable.data import DatasetConfig, generate_dataset
from timetable.models import UniversityDataset
from timetable.render import render_outputs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="University timetable generator and solver."
    )
    subparsers = parser.add_subparsers(dest="command")

    generate_parser = subparsers.add_parser(
        "generate-data",
        help="Generate dummy university data without solving the timetable.",
    )
    add_dataset_arguments(generate_parser)
    generate_parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/university_dataset.json"),
        help="Path to the generated dataset JSON file.",
    )

    solve_parser = subparsers.add_parser(
        "solve",
        help="Solve a timetable from an existing dataset JSON file.",
    )
    solve_parser.add_argument(
        "--data",
        type=Path,
        default=None,
        help="Path to an existing dataset JSON file. Defaults to the latest dataset under outputs.",
    )
    solve_parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs"),
        help="Directory for rendered schedules.",
    )
    solve_parser.add_argument(
        "--time-limit",
        type=int,
        default=300,
        help="Maximum solver runtime in seconds.",
    )

    demo_parser = subparsers.add_parser(
        "demo",
        help="Generate data, solve the timetable, and render HTML reports.",
    )
    add_dataset_arguments(demo_parser)
    demo_parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs"),
        help="Directory for generated data and rendered schedules.",
    )
    demo_parser.add_argument(
        "--time-limit",
        type=int,
        default=300,
        help="Maximum solver runtime in seconds.",
    )

    return parser


def add_dataset_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--seed",
        type=int,
        default=17,
        help="Random seed used for deterministic dummy data generation.",
    )
    parser.add_argument(
        "--program-count",
        type=int,
        default=8,
        help="How many study programs to include.",
    )
    parser.add_argument(
        "--years-per-program",
        type=int,
        default=3,
        help="How many years to include for each program.",
    )
    parser.add_argument(
        "--courses-per-year",
        type=int,
        default=5,
        help="How many subjects to generate for every program year.",
    )


def build_dataset_config(args: argparse.Namespace) -> DatasetConfig:
    return DatasetConfig(
        random_seed=args.seed,
        program_count=args.program_count,
        years_per_program=args.years_per_program,
        courses_per_year=args.courses_per_year,
    )


def run_generate_data(args: argparse.Namespace) -> None:
    dataset = generate_dataset(build_dataset_config(args))
    output_path = create_output_path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    dataset.save(output_path)
    print(f"Output directory: {output_path.parent}")
    print(f"Dataset saved to {output_path}")
    print_dataset_stats(dataset)


def run_solve(args: argparse.Namespace) -> None:
    SolveOptions, solve_timetable = load_solver()
    data_path = resolve_dataset_path(args.data)
    dataset = UniversityDataset.load(data_path)
    try:
        result = solve_timetable(
            dataset,
            SolveOptions(time_limit_seconds=args.time_limit),
        )
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc
    run_output_dir = create_run_output_dir(args.output_dir)
    artifacts = render_outputs(dataset, result, run_output_dir)
    print(f"Input dataset: {data_path}")
    print(f"Output directory: {artifacts.output_dir}")
    print(f"Schedule solved with status {result.status}")
    print(f"Summary: {artifacts.summary_markdown}")
    print(f"Teachers: {artifacts.teacher_html}")
    print(f"Subjects: {artifacts.subject_html}")
    print(f"Cohorts: {artifacts.cohort_html}")
    print(f"Rooms: {artifacts.room_html}")


def run_demo(args: argparse.Namespace) -> None:
    SolveOptions, solve_timetable = load_solver()
    output_dir = create_run_output_dir(args.output_dir)

    dataset = generate_dataset(build_dataset_config(args))
    dataset_path = output_dir / "university_dataset.json"
    dataset.save(dataset_path)

    try:
        result = solve_timetable(
            dataset,
            SolveOptions(time_limit_seconds=args.time_limit, random_seed=args.seed),
        )
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc
    artifacts = render_outputs(dataset, result, output_dir)

    print(f"Output directory: {artifacts.output_dir}")
    print(f"Dataset saved to {dataset_path}")
    print(f"Schedule solved with status {result.status}")
    print(f"Summary: {artifacts.summary_markdown}")
    print(f"Teachers: {artifacts.teacher_html}")
    print(f"Subjects: {artifacts.subject_html}")
    print(f"Cohorts: {artifacts.cohort_html}")
    print(f"Rooms: {artifacts.room_html}")


def print_dataset_stats(dataset: UniversityDataset) -> None:
    print(
        "Generated "
        f"{len(dataset.teachers)} teachers, "
        f"{len(dataset.rooms)} rooms, "
        f"{len(dataset.cohorts)} cohorts, "
        f"{len(dataset.study_groups)} study groups, "
        f"and {len(dataset.courses)} courses."
    )


def load_solver():
    try:
        from timetable.solver import SolveOptions, solve_timetable
    except ModuleNotFoundError as exc:
        if exc.name != "ortools":
            raise
        raise SystemExit(
            "Missing dependency 'ortools'. Run 'python -m pip install -r requirements.txt' "
            "or use the project virtual environment."
        ) from exc
    return SolveOptions, solve_timetable


def create_output_path(requested_path: Path) -> Path:
    run_output_dir = create_run_output_dir(requested_path.parent)
    return run_output_dir / requested_path.name


def create_run_output_dir(base_dir: Path) -> Path:
    base_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_output_dir = base_dir / timestamp
    counter = 1
    while run_output_dir.exists():
        counter += 1
        run_output_dir = base_dir / f"{timestamp}_{counter:02d}"
    run_output_dir.mkdir(parents=True, exist_ok=False)
    return run_output_dir


def resolve_dataset_path(requested_path: Path | None) -> Path:
    if requested_path is not None:
        return requested_path

    candidates = sorted(
        Path("outputs").glob("*/university_dataset.json"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    if candidates:
        return candidates[0]
    raise SystemExit(
        "No dataset found under outputs. Run 'python main.py generate-data' or 'python main.py demo' first."
    )


def main() -> None:
    parser = build_parser()
    args = parser.parse_args(["demo"] if len(sys.argv) == 1 else None)
    command = args.command

    if command == "generate-data":
        run_generate_data(args)
    elif command == "solve":
        run_solve(args)
    elif command == "demo":
        run_demo(args)
    else:
        parser.error(f"Unsupported command: {command}")


if __name__ == "__main__":
    main()
