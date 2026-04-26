from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from html import escape
from pathlib import Path

from timetable.models import (
    DAY_CODES,
    DAY_LABELS,
    SLOTS_PER_DAY,
    STANDARD_BLOCK_TIMES,
    ScheduleResult,
    ScheduledSession,
    UniversityDataset,
)


@dataclass(frozen=True)
class RenderedArtifacts:
    output_dir: Path
    schedule_json: Path
    summary_markdown: Path
    teacher_html: Path
    subject_html: Path
    cohort_html: Path
    room_html: Path


def render_outputs(
    dataset: UniversityDataset,
    result: ScheduleResult,
    output_dir: Path,
) -> RenderedArtifacts:
    output_dir.mkdir(parents=True, exist_ok=True)

    schedule_json = output_dir / "schedule.json"
    summary_markdown = output_dir / "summary.md"
    teacher_html = output_dir / "teacher_timetables.html"
    subject_html = output_dir / "subject_timetables.html"
    cohort_html = output_dir / "cohort_timetables.html"
    room_html = output_dir / "room_timetables.html"

    result.save(schedule_json)
    summary_markdown.write_text(build_summary(dataset, result), encoding="utf-8")
    teacher_html.write_text(
        build_timetable_page(
            title="Teacher Timetables",
            subtitle="Schedules optimized mainly for minimum teacher attendance days.",
            entities=[
                {
                    "id": teacher.id,
                    "title": f"{teacher.name} ({teacher.department})",
                    "sessions": [
                        session
                        for session in result.sessions
                        if session.teacher_id == teacher.id
                    ],
                    "card_mode": "teacher",
                }
                for teacher in sorted(dataset.teachers, key=lambda item: item.name)
                if any(session.teacher_id == teacher.id for session in result.sessions)
            ],
        ),
        encoding="utf-8",
    )
    subject_html.write_text(
        build_timetable_page(
            title="Subject Timetables",
            subtitle="Lecture and practical placements for every generated subject.",
            entities=[
                {
                    "id": course.id,
                    "title": f"{course.code} {course.name} ({course.cohort_id})",
                    "sessions": [
                        session
                        for session in result.sessions
                        if session.course_id == course.id
                    ],
                    "card_mode": "subject",
                }
                for course in dataset.courses
            ],
        ),
        encoding="utf-8",
    )
    cohort_html.write_text(
        build_timetable_page(
            title="Cohort Timetables",
            subtitle="Compact view of student cohort schedules used for the secondary objective.",
            entities=[
                {
                    "id": cohort.id,
                    "title": f"{cohort.program_name} year {cohort.year} ({cohort.size} students)",
                    "sessions": [
                        session
                        for session in result.sessions
                        if session.cohort_id == cohort.id
                    ],
                    "card_mode": "cohort",
                }
                for cohort in dataset.cohorts
            ],
        ),
        encoding="utf-8",
    )
    room_html.write_text(
        build_timetable_page(
            title="Room Timetables",
            subtitle="Occupancy view for every lecture hall, lab, and seminar room.",
            entities=[
                {
                    "id": room.id,
                    "title": (
                        f"{room.name} "
                        f"({room.building}, cap {room.capacity}, {', '.join(room.features)})"
                    ),
                    "sessions": [
                        session
                        for session in result.sessions
                        if session.room_id == room.id
                    ],
                    "card_mode": "room",
                }
                for room in sorted(dataset.rooms, key=lambda item: item.name)
                if any(session.room_id == room.id for session in result.sessions)
            ],
        ),
        encoding="utf-8",
    )

    return RenderedArtifacts(
        output_dir=output_dir,
        schedule_json=schedule_json,
        summary_markdown=summary_markdown,
        teacher_html=teacher_html,
        subject_html=subject_html,
        cohort_html=cohort_html,
        room_html=room_html,
    )


def build_summary(dataset: UniversityDataset, result: ScheduleResult) -> str:
    sessions_total = len(result.sessions)
    lectures = sum(1 for session in result.sessions if session.session_kind == "lecture")
    practicals = sessions_total - lectures
    teacher_day_distribution = build_teacher_day_distribution(result.sessions)
    lines = [
        "# Timetable Summary",
        "",
        f"- Solver status: `{result.status}`",
        f"- Objective value: `{result.objective_value:.0f}`",
        f"- Teachers: `{len(dataset.teachers)}`",
        f"- Rooms: `{len(dataset.rooms)}`",
        f"- Cohorts: `{len(dataset.cohorts)}`",
        f"- Study groups: `{len(dataset.study_groups)}`",
        f"- Courses: `{len(dataset.courses)}`",
        f"- Scheduled sessions: `{sessions_total}`",
        f"- Lecture sessions: `{lectures}`",
        f"- Practical sessions: `{practicals}`",
        f"- Teacher-day usages: `{result.teacher_days}`",
        f"- Teacher single-class days: `{result.teacher_single_days}`",
        f"- Teacher double-block days: `{result.teacher_double_block_days}`",
        f"- Student-group day usages: `{result.group_days}`",
        f"- Late block sessions: `{result.late_sessions}`",
        "",
        "Teacher day distribution:",
    ]
    lines.extend(
        f"- `{day_count} {'day' if day_count == 1 else 'days'}`: `{teacher_count}` teachers"
        for day_count, teacher_count in teacher_day_distribution
    )
    lines.extend([
        "",
        "Files:",
        "- `schedule.json` contains the machine-readable schedule.",
        "- `teacher_timetables.html` contains one timetable per teacher.",
        "- `subject_timetables.html` contains one timetable per subject.",
        "- `cohort_timetables.html` contains one timetable per study cohort.",
        "- `room_timetables.html` contains one timetable per room.",
    ])
    return "\n".join(lines) + "\n"


def build_teacher_day_distribution(
    sessions: list[ScheduledSession],
) -> list[tuple[int, int]]:
    teacher_days: dict[str, set[str]] = defaultdict(set)
    for session in sessions:
        teacher_days[session.teacher_id].add(session.day_code)

    distribution: dict[int, int] = defaultdict(int)
    for days in teacher_days.values():
        distribution[len(days)] += 1

    return sorted(distribution.items())


def build_timetable_page(title: str, subtitle: str, entities: list[dict]) -> str:
    index_links = "\n".join(
        f'<a class="index-link" href="#{escape(anchor_id(entity["id"]))}">{escape(entity["title"])}</a>'
        for entity in entities
    )
    sections = "\n".join(
        build_entity_section(
            entity_id=entity["id"],
            title=entity["title"],
            sessions=entity["sessions"],
            card_mode=entity["card_mode"],
        )
        for entity in entities
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{escape(title)}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f5f3eb;
      --panel: #fffdfa;
      --ink: #1f2f21;
      --muted: #5f6b61;
      --grid: #d5dbd0;
      --accent: #244f2a;
      --lecture: #d9efe0;
      --practical: #f6ead5;
      --empty: #f7f7f2;
    }}
    * {{
      box-sizing: border-box;
    }}
    body {{
      margin: 0;
      font-family: "Segoe UI", Tahoma, sans-serif;
      background:
        radial-gradient(circle at top left, rgba(36, 79, 42, 0.08), transparent 35%),
        linear-gradient(180deg, #fbfaf7 0%, var(--bg) 100%);
      color: var(--ink);
    }}
    header {{
      padding: 32px 40px 20px;
      background: linear-gradient(135deg, #fefcf6 0%, #eef4e8 100%);
      border-bottom: 1px solid var(--grid);
      position: sticky;
      top: 0;
      z-index: 2;
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: 30px;
    }}
    .subtitle {{
      margin: 0;
      color: var(--muted);
      max-width: 960px;
    }}
    .index {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      gap: 10px;
      padding: 20px 40px 0;
    }}
    .index-link {{
      display: block;
      padding: 10px 12px;
      background: rgba(255, 255, 255, 0.85);
      border: 1px solid var(--grid);
      border-radius: 10px;
      color: var(--accent);
      text-decoration: none;
      font-size: 14px;
    }}
    .content {{
      padding: 24px 40px 48px;
    }}
    section {{
      margin-bottom: 32px;
      background: rgba(255, 253, 250, 0.92);
      border: 1px solid var(--grid);
      border-radius: 16px;
      padding: 18px 18px 22px;
      box-shadow: 0 8px 20px rgba(31, 47, 33, 0.05);
    }}
    h2 {{
      margin: 0 0 12px;
      font-size: 20px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      table-layout: fixed;
    }}
    th, td {{
      border: 1px solid var(--grid);
      vertical-align: top;
      padding: 8px;
    }}
    th {{
      background: #e5efe3;
      font-size: 13px;
    }}
    td {{
      background: var(--empty);
      min-height: 112px;
      height: 112px;
    }}
    .entry {{
      border-radius: 8px;
      padding: 6px 8px;
      margin-bottom: 6px;
      font-size: 12px;
      line-height: 1.35;
      border: 1px solid rgba(36, 79, 42, 0.12);
    }}
    .entry.lecture {{
      background: var(--lecture);
    }}
    .entry.practical {{
      background: var(--practical);
    }}
    .entry strong {{
      display: block;
      margin-bottom: 4px;
    }}
    .badge {{
      display: inline-block;
      margin-top: 4px;
      padding: 2px 6px;
      border-radius: 999px;
      background: rgba(36, 79, 42, 0.12);
      font-size: 11px;
    }}
    .empty {{
      color: #8d948d;
      font-size: 12px;
    }}
    @media (max-width: 960px) {{
      header, .content, .index {{
        padding-left: 18px;
        padding-right: 18px;
      }}
      th, td {{
        font-size: 11px;
        padding: 6px;
      }}
      td {{
        height: 140px;
      }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>{escape(title)}</h1>
    <p class="subtitle">{escape(subtitle)}</p>
  </header>
  <div class="index">
    {index_links}
  </div>
  <main class="content">
    {sections}
  </main>
</body>
</html>
"""


def build_entity_section(
    entity_id: str,
    title: str,
    sessions: list[ScheduledSession],
    card_mode: str,
) -> str:
    grid: dict[tuple[int, int], list[ScheduledSession]] = defaultdict(list)
    for session in sessions:
        grid[(DAY_CODES.index(session.day_code), session.slot_id % SLOTS_PER_DAY)].append(session)

    rows = []
    for day_index, day_code in enumerate(DAY_CODES):
        cells = []
        for block_index, (start, end) in enumerate(STANDARD_BLOCK_TIMES):
            entries = sorted(
                grid.get((day_index, block_index), []),
                key=lambda item: (
                    0 if item.week_pattern == "all" else 1,
                    item.course_code,
                    item.room_name,
                    item.teacher_name,
                ),
            )
            if entries:
                cell_html = "".join(build_entry(session, card_mode) for session in entries)
            else:
                cell_html = '<div class="empty">No class</div>'
            cells.append(f"<td>{cell_html}</td>")
        rows.append(
            f"<tr><th>{escape(DAY_LABELS[day_code])}</th>{''.join(cells)}</tr>"
        )

    header_cells = "".join(
        f"<th>{escape(start)}<br>{escape(end)}</th>" for start, end in STANDARD_BLOCK_TIMES
    )
    return f"""
<section id="{escape(anchor_id(entity_id))}">
  <h2>{escape(title)}</h2>
  <table>
    <thead>
      <tr>
        <th>Day</th>
        {header_cells}
      </tr>
    </thead>
    <tbody>
      {''.join(rows)}
    </tbody>
  </table>
</section>
"""


def build_entry(session: ScheduledSession, card_mode: str) -> str:
    badge = week_pattern_label(session.week_pattern)
    if card_mode == "teacher":
        detail = (
            f"{session.course_code} {session.course_name}<br>"
            f"{escape(session.room_name)}<br>"
            f"{escape(session.cohort_id)} / {escape(format_audience(session.audience_group_ids))}"
        )
    elif card_mode == "subject":
        detail = (
            f"{escape(session.teacher_name)}<br>"
            f"{escape(session.room_name)}<br>"
            f"{escape(format_audience(session.audience_group_ids))}"
        )
    elif card_mode == "room":
        detail = (
            f"{session.course_code} {session.course_name}<br>"
            f"{escape(session.teacher_name)}<br>"
            f"{escape(format_audience(session.audience_group_ids))}"
        )
    else:
        detail = (
            f"{session.course_code} {session.course_name}<br>"
            f"{escape(session.teacher_name)}<br>"
            f"{escape(session.room_name)}"
        )
    kind = "lecture" if session.session_kind == "lecture" else "practical"
    kind_label = "Prednaska" if session.session_kind == "lecture" else "Cviceni"
    return (
        f'<div class="entry {kind}">'
        f"<strong>{escape(kind_label)}</strong>"
        f"{detail}<br>"
        f'<span class="badge">{escape(badge)}</span>'
        f"</div>"
    )


def week_pattern_label(pattern: str) -> str:
    if pattern == "all":
        return "kazdy tyden"
    if pattern == "odd":
        return "liche tydny"
    return "sude tydny"


def format_audience(group_ids: list[str]) -> str:
    if len(group_ids) <= 2:
        return ", ".join(group_ids)
    return f"{len(group_ids)} groups"


def anchor_id(value: str) -> str:
    return value.lower().replace(" ", "-").replace("/", "-")
