from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from main import create_output_path, create_run_output_dir
from timetable.data import DatasetConfig, generate_dataset
from timetable.render import render_outputs
from timetable.solver import SolveOptions, solve_timetable


def week_patterns_overlap(left: str, right: str) -> bool:
    left_weeks = {"odd", "even"} if left == "all" else {left}
    right_weeks = {"odd", "even"} if right == "all" else {right}
    return bool(left_weeks & right_weeks)


class TimetableTests(unittest.TestCase):
    def test_dataset_has_university_scale(self) -> None:
        dataset = generate_dataset()

        self.assertEqual(len(dataset.cohorts), 24)
        self.assertEqual(len(dataset.courses), 120)
        self.assertEqual(len(dataset.rooms), 59)
        self.assertEqual(len(dataset.teachers), 88)
        self.assertGreaterEqual(len(dataset.study_groups), 96)
        self.assertEqual(
            len([room for room in dataset.rooms if "lecture_hall" in room.features]),
            8,
        )
        self.assertTrue(all(teacher.preferred_day_codes for teacher in dataset.teachers))
        self.assertTrue(any(teacher.avoid_single_block_days for teacher in dataset.teachers))
        self.assertTrue(all(teacher.preferred_max_teaching_days == 2 for teacher in dataset.teachers))
        self.assertTrue(all(teacher.absolute_max_teaching_days == 3 for teacher in dataset.teachers))

    def test_small_instance_solves_without_resource_conflicts(self) -> None:
        dataset = generate_dataset(
            DatasetConfig(
                random_seed=7,
                program_count=2,
                years_per_program=1,
                courses_per_year=3,
            )
        )
        result = solve_timetable(
            dataset,
            SolveOptions(time_limit_seconds=20, random_seed=7, num_workers=4),
        )

        room_usage: dict[tuple[str, int], list] = {}
        teacher_usage: dict[tuple[str, int], list] = {}
        group_usage: dict[tuple[str, int], list] = {}

        for session in result.sessions:
            room_usage.setdefault((session.room_id, session.slot_id), []).append(session)
            teacher_usage.setdefault((session.teacher_id, session.slot_id), []).append(session)
            for group_id in session.audience_group_ids:
                group_usage.setdefault((group_id, session.slot_id), []).append(session)

        for usage in (room_usage, teacher_usage, group_usage):
            for sessions in usage.values():
                for index, left in enumerate(sessions):
                    for right in sessions[index + 1 :]:
                        self.assertFalse(
                            week_patterns_overlap(left.week_pattern, right.week_pattern),
                            msg=f"Conflicting sessions found: {left.session_id} and {right.session_id}",
                        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            artifacts = render_outputs(dataset, result, Path(tmp_dir))
            self.assertTrue(artifacts.output_dir.exists())
            self.assertTrue(artifacts.schedule_json.exists())
            self.assertTrue(artifacts.teacher_html.exists())
            self.assertTrue(artifacts.subject_html.exists())
            self.assertTrue(artifacts.cohort_html.exists())
            self.assertTrue(artifacts.room_html.exists())

    def test_output_paths_create_timestamped_subdirectories(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_dir = Path(tmp_dir) / "outputs"
            first_dir = create_run_output_dir(base_dir)
            second_dir = create_run_output_dir(base_dir)

            self.assertTrue(first_dir.exists())
            self.assertTrue(second_dir.exists())
            self.assertNotEqual(first_dir, second_dir)
            self.assertEqual(first_dir.parent, base_dir)
            self.assertEqual(second_dir.parent, base_dir)

            output_path = create_output_path(base_dir / "university_dataset.json")
            self.assertEqual(output_path.parent.parent, base_dir)
            self.assertEqual(output_path.name, "university_dataset.json")


if __name__ == "__main__":
    unittest.main()
