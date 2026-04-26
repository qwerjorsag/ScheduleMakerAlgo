from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from typing import Any


DAY_CODES = ("MON", "TUE", "WED", "THU", "FRI")
DAY_LABELS = {
    "MON": "Po",
    "TUE": "Ut",
    "WED": "St",
    "THU": "Ct",
    "FRI": "Pa",
}
STANDARD_BLOCK_TIMES = (
    ("08:45", "10:15"),
    ("10:30", "12:00"),
    ("12:15", "13:45"),
    ("14:00", "15:30"),
    ("15:45", "17:15"),
    ("17:30", "19:00"),
    ("19:15", "20:45"),
)
SLOTS_PER_DAY = len(STANDARD_BLOCK_TIMES)

WEEK_PATTERN_ALL = "all"
WEEK_PATTERN_ODD = "odd"
WEEK_PATTERN_EVEN = "even"
SESSION_KIND_LECTURE = "lecture"
SESSION_KIND_PRACTICAL = "practical"


@dataclass(frozen=True)
class TimeBlock:
    index: int
    day_index: int
    day_code: str
    day_label: str
    block_index: int
    start: str
    end: str


def build_time_blocks() -> list[TimeBlock]:
    blocks: list[TimeBlock] = []
    slot_index = 0
    for day_index, day_code in enumerate(DAY_CODES):
        for block_index, (start, end) in enumerate(STANDARD_BLOCK_TIMES):
            blocks.append(
                TimeBlock(
                    index=slot_index,
                    day_index=day_index,
                    day_code=day_code,
                    day_label=DAY_LABELS[day_code],
                    block_index=block_index,
                    start=start,
                    end=end,
                )
            )
            slot_index += 1
    return blocks


TIME_BLOCKS = tuple(build_time_blocks())


@dataclass
class Teacher:
    id: str
    name: str
    department: str
    subjects: list[str]
    unavailable_slot_ids: list[int]
    preferred_day_codes: list[str] = field(default_factory=list)
    avoid_single_block_days: bool = False
    preferred_max_teaching_days: int = 3
    absolute_max_teaching_days: int = 4


@dataclass
class Room:
    id: str
    name: str
    capacity: int
    building: str
    features: list[str]


@dataclass
class Cohort:
    id: str
    program_id: str
    program_name: str
    year: int
    size: int
    group_count: int


@dataclass
class StudyGroup:
    id: str
    cohort_id: str
    name: str
    size: int


@dataclass
class Course:
    id: str
    code: str
    name: str
    program_id: str
    program_name: str
    year: int
    cohort_id: str
    student_count: int
    lecture_teacher_id: str
    practical_teacher_by_group: dict[str, str]
    lecture_room_features: list[str]
    practical_room_features: list[str]
    lecture_blocks_per_week: int
    practical_frequency: str
    practical_group_size: int


@dataclass
class SessionRequest:
    id: str
    course_id: str
    course_code: str
    course_name: str
    teacher_id: str
    teacher_name: str
    cohort_id: str
    audience_group_ids: list[str]
    session_kind: str
    week_pattern: str
    allowed_room_features: list[str]
    min_capacity: int
    display_label: str


@dataclass
class ScheduledSession:
    session_id: str
    course_id: str
    course_code: str
    course_name: str
    teacher_id: str
    teacher_name: str
    cohort_id: str
    audience_group_ids: list[str]
    session_kind: str
    week_pattern: str
    room_id: str
    room_name: str
    day_code: str
    day_label: str
    start: str
    end: str
    slot_id: int
    display_label: str


@dataclass
class ScheduleResult:
    sessions: list[ScheduledSession]
    objective_value: float
    teacher_days: int
    teacher_single_days: int
    teacher_double_block_days: int
    group_days: int
    late_sessions: int
    status: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "sessions": [asdict(session) for session in self.sessions],
            "objective_value": self.objective_value,
            "teacher_days": self.teacher_days,
            "teacher_single_days": self.teacher_single_days,
            "teacher_double_block_days": self.teacher_double_block_days,
            "group_days": self.group_days,
            "late_sessions": self.late_sessions,
            "status": self.status,
        }

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ScheduleResult:
        return cls(
            sessions=[ScheduledSession(**session) for session in payload["sessions"]],
            objective_value=payload["objective_value"],
            teacher_days=payload["teacher_days"],
            teacher_single_days=payload["teacher_single_days"],
            teacher_double_block_days=payload["teacher_double_block_days"],
            group_days=payload["group_days"],
            late_sessions=payload["late_sessions"],
            status=payload["status"],
        )

    @classmethod
    def load(cls, path: Path) -> ScheduleResult:
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))


@dataclass
class UniversityDataset:
    teachers: list[Teacher]
    rooms: list[Room]
    cohorts: list[Cohort]
    study_groups: list[StudyGroup]
    courses: list[Course]
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "teachers": [asdict(teacher) for teacher in self.teachers],
            "rooms": [asdict(room) for room in self.rooms],
            "cohorts": [asdict(cohort) for cohort in self.cohorts],
            "study_groups": [asdict(group) for group in self.study_groups],
            "courses": [asdict(course) for course in self.courses],
            "meta": self.meta,
        }

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> UniversityDataset:
        return cls(
            teachers=[Teacher(**teacher) for teacher in payload["teachers"]],
            rooms=[Room(**room) for room in payload["rooms"]],
            cohorts=[Cohort(**cohort) for cohort in payload["cohorts"]],
            study_groups=[StudyGroup(**group) for group in payload["study_groups"]],
            courses=[Course(**course) for course in payload["courses"]],
            meta=payload.get("meta", {}),
        )

    @classmethod
    def load(cls, path: Path) -> UniversityDataset:
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))


def slot_for(day_code: str, block_index: int) -> TimeBlock:
    day_index = DAY_CODES.index(day_code)
    return TIME_BLOCKS[day_index * SLOTS_PER_DAY + block_index]
