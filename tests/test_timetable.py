from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from main import create_output_path, create_run_output_dir
from timetable.data import DatasetConfig, generate_dataset
from timetable.editor import ScheduleEditor
from timetable.final_control import validate_schedule
from timetable.models import ScheduleResult, UniversityDataset
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
            teacher_html = artifacts.teacher_html.read_text(encoding="utf-8")
            self.assertIn("Nastaveni", teacher_html)
            self.assertIn("teacher-unavailable", teacher_html)
            self.assertIn("Studentu:", teacher_html)

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

    def test_editor_persists_slot_change(self) -> None:
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

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir)
            render_outputs(dataset, result, output_dir)
            dataset.save(output_dir / "university_dataset.json")

            editor = ScheduleEditor(output_dir)
            moving_session = next(
                session
                for session in editor.result.sessions
                if len(editor.get_valid_targets(session.session_id)) > 1
            )
            target = next(
                slot
                for slot in editor.get_valid_targets(moving_session.session_id)
                if slot["slot_id"] != moving_session.slot_id
            )
            room = editor.get_valid_rooms(
                moving_session.session_id,
                target["slot_id"],
                week_pattern=moving_session.week_pattern,
            )[0]

            editor.move_session(
                moving_session.session_id,
                target["slot_id"],
                room_id=room["room_id"],
            )

            reloaded_schedule = ScheduleResult.load(output_dir / "schedule.json")
            updated_session = next(
                session
                for session in reloaded_schedule.sessions
                if session.session_id == moving_session.session_id
            )
            self.assertEqual(updated_session.slot_id, target["slot_id"])
            self.assertEqual(updated_session.day_code, target["day_code"])

            reloaded_dataset = UniversityDataset.load(output_dir / "university_dataset.json")
            self.assertEqual(
                reloaded_dataset.meta["manual_schedule_overrides"][moving_session.session_id]["slot_id"],
                target["slot_id"],
            )

    def test_editor_persists_week_pattern_change(self) -> None:
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

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir)
            render_outputs(dataset, result, output_dir)
            dataset.save(output_dir / "university_dataset.json")

            editor = ScheduleEditor(output_dir)
            candidate = next(
                (
                    session,
                    "odd" if session.week_pattern == "even" else "even",
                )
                for session in editor.result.sessions
                if session.week_pattern in {"odd", "even"}
                and editor.get_valid_targets(
                    session.session_id,
                    week_pattern="odd" if session.week_pattern == "even" else "even",
                )
            )
            moving_session, new_pattern = candidate
            valid_targets = editor.get_valid_targets(moving_session.session_id, week_pattern=new_pattern)
            target = next((slot for slot in valid_targets if slot["slot_id"] == moving_session.slot_id), valid_targets[0])
            room = editor.get_valid_rooms(
                moving_session.session_id,
                target["slot_id"],
                week_pattern=new_pattern,
            )[0]

            editor.move_session(
                moving_session.session_id,
                target["slot_id"],
                week_pattern=new_pattern,
                room_id=room["room_id"],
            )

            reloaded_schedule = ScheduleResult.load(output_dir / "schedule.json")
            updated_session = next(
                session
                for session in reloaded_schedule.sessions
                if session.session_id == moving_session.session_id
            )
            self.assertEqual(updated_session.week_pattern, new_pattern)

    def test_editor_never_offers_teacher_unavailable_slots(self) -> None:
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

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir)
            render_outputs(dataset, result, output_dir)
            dataset.save(output_dir / "university_dataset.json")

            editor = ScheduleEditor(output_dir)
            teacher_by_id = {teacher.id: teacher for teacher in dataset.teachers}

            for session in editor.result.sessions[:40]:
                teacher = teacher_by_id[session.teacher_id]
                valid_slot_ids = {
                    slot["slot_id"] for slot in editor.get_valid_targets(session.session_id)
                }
                self.assertTrue(valid_slot_ids.isdisjoint(set(teacher.unavailable_slot_ids)))

    def test_editor_never_offers_occupied_rooms(self) -> None:
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

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir)
            render_outputs(dataset, result, output_dir)
            dataset.save(output_dir / "university_dataset.json")

            editor = ScheduleEditor(output_dir)

            for session in editor.result.sessions[:40]:
                valid_rooms = editor.get_valid_rooms(
                    session.session_id,
                    session.slot_id,
                    week_pattern=session.week_pattern,
                )
                valid_room_ids = {room["room_id"] for room in valid_rooms}
                blocked_room_ids = {
                    other.room_id
                    for other in editor.result.sessions
                    if other.session_id != session.session_id
                    and other.slot_id == session.slot_id
                    and week_patterns_overlap(other.week_pattern, session.week_pattern)
                }
                self.assertTrue(valid_room_ids.isdisjoint(blocked_room_ids))

    def test_editor_persists_room_change(self) -> None:
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

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir)
            render_outputs(dataset, result, output_dir)
            dataset.save(output_dir / "university_dataset.json")

            editor = ScheduleEditor(output_dir)
            moving_session, valid_rooms = next(
                (
                    session,
                    editor.get_valid_rooms(
                        session.session_id,
                        session.slot_id,
                        week_pattern=session.week_pattern,
                    ),
                )
                for session in editor.result.sessions
                if len(
                    editor.get_valid_rooms(
                        session.session_id,
                        session.slot_id,
                        week_pattern=session.week_pattern,
                    )
                ) > 1
            )
            target_room = next(room for room in valid_rooms if room["room_id"] != moving_session.room_id)

            editor.move_session(
                moving_session.session_id,
                moving_session.slot_id,
                week_pattern=moving_session.week_pattern,
                room_id=target_room["room_id"],
            )

            reloaded_schedule = ScheduleResult.load(output_dir / "schedule.json")
            updated_session = next(
                session
                for session in reloaded_schedule.sessions
                if session.session_id == moving_session.session_id
            )
            self.assertEqual(updated_session.room_id, target_room["room_id"])

    def test_final_control_accepts_valid_schedule(self) -> None:
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

        self.assertEqual(validate_schedule(result), [])


if __name__ == "__main__":
    unittest.main()
