from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

from timetable.models import (
    DAY_CODES,
    DAY_LABELS,
    SESSION_KIND_LECTURE,
    ScheduleResult,
    ScheduledSession,
    SLOTS_PER_DAY,
    TIME_BLOCKS,
    UniversityDataset,
)
from timetable.render import render_outputs


class MoveValidationError(ValueError):
    pass


class ScheduleEditor:
    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.dataset_path = output_dir / "university_dataset.json"
        self.schedule_path = output_dir / "schedule.json"
        self.dataset = UniversityDataset.load(self.dataset_path)
        self.result = ScheduleResult.load(self.schedule_path)
        self.teacher_unavailable_slots = {
            teacher.id: set(teacher.unavailable_slot_ids)
            for teacher in self.dataset.teachers
        }
        self.rooms_by_id = {room.id: room for room in self.dataset.rooms}
        self.courses_by_id = {course.id: course for course in self.dataset.courses}
        self.groups_by_id = {group.id: group for group in self.dataset.study_groups}

    def get_valid_targets(self, session_id: str, week_pattern: str | None = None) -> list[dict[str, Any]]:
        session = self.get_session_with_week_pattern(session_id, week_pattern)
        targets: list[dict[str, Any]] = []
        for slot in TIME_BLOCKS:
            if self.is_slot_allowed(session, slot.index):
                targets.append(slot_to_payload(slot.index))
        return targets

    def get_valid_rooms(
        self,
        session_id: str,
        slot_id: int,
        week_pattern: str | None = None,
    ) -> list[dict[str, Any]]:
        session = self.get_session_with_week_pattern(session_id, week_pattern)
        return [
            room_to_payload(room)
            for room in self.dataset.rooms
            if self.is_room_allowed(session, slot_id, room.id)
        ]

    def move_session(
        self,
        session_id: str,
        slot_id: int,
        week_pattern: str | None = None,
        room_id: str | None = None,
    ) -> dict[str, Any]:
        session = self.get_session_with_week_pattern(session_id, week_pattern)
        if room_id is None:
            room_id = session.room_id
        if not self.is_slot_allowed(session, slot_id):
            raise MoveValidationError("Selected target slot is not allowed for this session.")
        if not self.is_room_allowed(session, slot_id, room_id):
            raise MoveValidationError("Selected room is not allowed for this session and slot.")

        target = TIME_BLOCKS[slot_id]
        room = self.rooms_by_id[room_id]
        moved = replace(
            session,
            slot_id=slot_id,
            day_code=target.day_code,
            day_label=target.day_label,
            start=target.start,
            end=target.end,
            room_id=room.id,
            room_name=room.name,
        )
        self.result.sessions = [
            moved if current.session_id == session_id else current
            for current in self.result.sessions
        ]
        self.persist()
        return {
            "session_id": moved.session_id,
            "slot": slot_to_payload(slot_id),
            "week_pattern": moved.week_pattern,
            "room": room_to_payload(room),
        }

    def persist(self) -> None:
        self.result.save(self.schedule_path)
        self.dataset.meta["manual_schedule_overrides"] = {
            session.session_id: {
                "slot_id": session.slot_id,
                "day_code": session.day_code,
                "day_label": session.day_label,
                "start": session.start,
                "end": session.end,
                "week_pattern": session.week_pattern,
                "room_id": session.room_id,
                "room_name": session.room_name,
            }
            for session in self.result.sessions
        }
        self.dataset.save(self.dataset_path)
        render_outputs(self.dataset, self.result, self.output_dir)

    def get_session(self, session_id: str) -> ScheduledSession:
        for session in self.result.sessions:
            if session.session_id == session_id:
                return session
        raise MoveValidationError(f"Unknown session id: {session_id}")

    def get_session_with_week_pattern(
        self,
        session_id: str,
        week_pattern: str | None,
    ) -> ScheduledSession:
        session = self.get_session(session_id)
        if week_pattern is None:
            return session
        validate_week_pattern(week_pattern)
        return replace(session, week_pattern=week_pattern)

    def is_slot_allowed(self, moving_session: ScheduledSession, slot_id: int) -> bool:
        if slot_id in self.teacher_unavailable_slots.get(moving_session.teacher_id, set()):
            return False
        for other in self.result.sessions:
            if other.session_id == moving_session.session_id:
                continue
            if other.slot_id != slot_id:
                continue
            if not week_patterns_overlap(moving_session.week_pattern, other.week_pattern):
                continue
            if other.teacher_id == moving_session.teacher_id:
                return False
            if other.cohort_id != moving_session.cohort_id:
                continue
            if other.session_kind == SESSION_KIND_LECTURE or moving_session.session_kind == SESSION_KIND_LECTURE:
                return False
            if set(other.audience_group_ids) & set(moving_session.audience_group_ids):
                return False
        return bool(self.get_valid_rooms_for_session(moving_session, slot_id))

    def is_room_allowed(self, moving_session: ScheduledSession, slot_id: int, room_id: str) -> bool:
        validate_room_id(room_id, self.rooms_by_id)
        room = self.rooms_by_id[room_id]
        required_features = set(self.required_room_features(moving_session))
        if not required_features.issubset(set(room.features)):
            return False
        if room.capacity < self.required_capacity(moving_session):
            return False
        for other in self.result.sessions:
            if other.session_id == moving_session.session_id:
                continue
            if other.slot_id != slot_id:
                continue
            if other.room_id != room_id:
                continue
            if week_patterns_overlap(moving_session.week_pattern, other.week_pattern):
                return False
        return True

    def get_valid_rooms_for_session(
        self,
        moving_session: ScheduledSession,
        slot_id: int,
    ) -> list[Any]:
        return [
            room
            for room in self.dataset.rooms
            if self.is_room_allowed(moving_session, slot_id, room.id)
        ]

    def required_room_features(self, session: ScheduledSession) -> list[str]:
        course = self.courses_by_id[session.course_id]
        if session.session_kind == SESSION_KIND_LECTURE:
            return course.lecture_room_features
        return course.practical_room_features

    def required_capacity(self, session: ScheduledSession) -> int:
        if session.session_kind == SESSION_KIND_LECTURE:
            return self.courses_by_id[session.course_id].student_count
        return sum(self.groups_by_id[group_id].size for group_id in session.audience_group_ids)


def week_patterns_overlap(left: str, right: str) -> bool:
    left_weeks = {"odd", "even"} if left == "all" else {left}
    right_weeks = {"odd", "even"} if right == "all" else {right}
    return bool(left_weeks & right_weeks)


def validate_week_pattern(week_pattern: str) -> None:
    if week_pattern not in {"all", "odd", "even"}:
        raise MoveValidationError(f"Unsupported week pattern: {week_pattern}")


def validate_room_id(room_id: str, rooms_by_id: dict[str, Any]) -> None:
    if room_id not in rooms_by_id:
        raise MoveValidationError(f"Unknown room id: {room_id}")


def slot_to_payload(slot_id: int) -> dict[str, Any]:
    block = TIME_BLOCKS[slot_id]
    return {
        "slot_id": slot_id,
        "day_code": block.day_code,
        "day_label": DAY_LABELS[block.day_code],
        "block_index": block.block_index,
        "start": block.start,
        "end": block.end,
        "slot_key": slot_key(block.day_code, block.block_index),
    }


def room_to_payload(room: Any) -> dict[str, Any]:
    return {
        "room_id": room.id,
        "room_name": room.name,
        "capacity": room.capacity,
        "building": room.building,
        "features": room.features,
        "label": f"{room.name} ({room.building}, cap {room.capacity}, {', '.join(room.features)})",
    }


def slot_key(day_code: str, block_index: int) -> str:
    return f"{day_code}:{block_index}"


def parse_slot_key(raw_slot_key: str) -> int:
    day_code, block_index_text = raw_slot_key.split(":", maxsplit=1)
    if day_code not in DAY_CODES:
        raise MoveValidationError(f"Unsupported day code: {day_code}")
    block_index = int(block_index_text)
    if block_index < 0 or block_index >= SLOTS_PER_DAY:
        raise MoveValidationError(f"Unsupported block index: {block_index}")
    return DAY_CODES.index(day_code) * SLOTS_PER_DAY + block_index
