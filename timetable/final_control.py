from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from timetable.models import ScheduleResult, ScheduledSession


@dataclass(frozen=True)
class ControlIssue:
    category: str
    message: str
    session_ids: tuple[str, ...]


def week_patterns_overlap(left: str, right: str) -> bool:
    left_weeks = {"odd", "even"} if left == "all" else {left}
    right_weeks = {"odd", "even"} if right == "all" else {right}
    return bool(left_weeks & right_weeks)


def validate_schedule(result: ScheduleResult) -> list[ControlIssue]:
    issues: list[ControlIssue] = []
    issues.extend(find_teacher_conflicts(result.sessions))
    issues.extend(find_room_conflicts(result.sessions))
    issues.extend(find_lecture_practical_conflicts(result.sessions))
    return issues


def find_teacher_conflicts(sessions: list[ScheduledSession]) -> list[ControlIssue]:
    return find_pair_conflicts(
        sessions,
        category="teacher_conflict",
        resource_key=lambda session: (session.teacher_id, session.slot_id),
        message_builder=lambda left, right: (
            f"Teacher {left.teacher_name} overlaps in slot {left.slot_id}: "
            f"{left.session_id} vs {right.session_id}"
        ),
    )


def find_room_conflicts(sessions: list[ScheduledSession]) -> list[ControlIssue]:
    return find_pair_conflicts(
        sessions,
        category="room_conflict",
        resource_key=lambda session: (session.room_id, session.slot_id),
        message_builder=lambda left, right: (
            f"Room {left.room_name} overlaps in slot {left.slot_id}: "
            f"{left.session_id} vs {right.session_id}"
        ),
    )


def find_lecture_practical_conflicts(sessions: list[ScheduledSession]) -> list[ControlIssue]:
    issues: list[ControlIssue] = []
    by_cohort_slot: dict[tuple[str, int], list[ScheduledSession]] = {}
    for session in sessions:
        by_cohort_slot.setdefault((session.cohort_id, session.slot_id), []).append(session)

    for cohort_slot_sessions in by_cohort_slot.values():
        for index, left in enumerate(cohort_slot_sessions):
            for right in cohort_slot_sessions[index + 1 :]:
                if not week_patterns_overlap(left.week_pattern, right.week_pattern):
                    continue
                if {left.session_kind, right.session_kind} != {"lecture", "practical"}:
                    continue
                lecture = left if left.session_kind == "lecture" else right
                practical = right if lecture is left else left
                issues.append(
                    ControlIssue(
                        category="lecture_practical_conflict",
                        message=(
                            f"Cohort {lecture.cohort_id} has lecture/practical overlap in slot "
                            f"{lecture.slot_id}: {lecture.session_id} vs {practical.session_id}"
                        ),
                        session_ids=(lecture.session_id, practical.session_id),
                    )
                )
    return issues


def find_pair_conflicts(
    sessions: list[ScheduledSession],
    category: str,
    resource_key,
    message_builder,
) -> list[ControlIssue]:
    issues: list[ControlIssue] = []
    grouped: dict[tuple[str, int], list[ScheduledSession]] = {}
    for session in sessions:
        grouped.setdefault(resource_key(session), []).append(session)

    for grouped_sessions in grouped.values():
        for index, left in enumerate(grouped_sessions):
            for right in grouped_sessions[index + 1 :]:
                if not week_patterns_overlap(left.week_pattern, right.week_pattern):
                    continue
                issues.append(
                    ControlIssue(
                        category=category,
                        message=message_builder(left, right),
                        session_ids=(left.session_id, right.session_id),
                    )
                )
    return issues


def run_final_control(output_dir: Path) -> int:
    schedule_path = output_dir / "schedule.json"
    result = ScheduleResult.load(schedule_path)
    issues = validate_schedule(result)

    print(f"Schedule checked: {schedule_path}")
    if not issues:
        print("OK: no teacher, room, or lecture/practical conflicts found.")
        return 0

    print(f"Found {len(issues)} conflict(s):")
    for issue in issues:
        print(f"- [{issue.category}] {issue.message}")
    return 1
