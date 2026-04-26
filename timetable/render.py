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
    session_sizes = build_session_sizes(dataset, result.sessions)

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
                    "unavailable_slot_ids": teacher.unavailable_slot_ids,
                }
                for teacher in sorted(dataset.teachers, key=lambda item: item.name)
                if any(session.teacher_id == teacher.id for session in result.sessions)
            ],
            session_sizes=session_sizes,
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
                    "unavailable_slot_ids": [],
                }
                for course in dataset.courses
            ],
            session_sizes=session_sizes,
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
                    "unavailable_slot_ids": [],
                }
                for cohort in dataset.cohorts
            ],
            session_sizes=session_sizes,
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
                    "unavailable_slot_ids": [],
                }
                for room in sorted(dataset.rooms, key=lambda item: item.name)
                if any(session.room_id == room.id for session in result.sessions)
            ],
            session_sizes=session_sizes,
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


def build_session_sizes(
    dataset: UniversityDataset,
    sessions: list[ScheduledSession],
) -> dict[str, int]:
    cohort_sizes = {cohort.id: cohort.size for cohort in dataset.cohorts}
    group_sizes = {group.id: group.size for group in dataset.study_groups}
    session_sizes: dict[str, int] = {}
    for session in sessions:
        if session.session_kind == "lecture":
            session_sizes[session.session_id] = cohort_sizes.get(session.cohort_id, 0)
        else:
            session_sizes[session.session_id] = sum(
                group_sizes.get(group_id, 0) for group_id in session.audience_group_ids
            )
    return session_sizes


def build_timetable_page(
    title: str,
    subtitle: str,
    entities: list[dict],
    session_sizes: dict[str, int],
) -> str:
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
            unavailable_slot_ids=entity.get("unavailable_slot_ids", []),
            session_sizes=session_sizes,
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
      --blocked: #f7d9d9;
      --blocked-ink: #8b2020;
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
      z-index: 3;
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
    .toolbar {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding: 14px 40px 0;
    }}
    .hint {{
      margin: 0;
      color: var(--muted);
      font-size: 13px;
    }}
    .status {{
      min-height: 20px;
      font-size: 13px;
      color: var(--accent);
      text-align: right;
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
    td.teacher-unavailable {{
      background: var(--blocked);
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
    .entry-top {{
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 8px;
      margin-bottom: 4px;
    }}
    .entry-title {{
      min-width: 0;
      flex: 1;
    }}
    .entry-actions {{
      flex: 0 0 auto;
    }}
    .settings-button {{
      border: 1px solid rgba(36, 79, 42, 0.22);
      background: rgba(255, 255, 255, 0.78);
      color: var(--accent);
      border-radius: 8px;
      padding: 4px 7px;
      font-size: 11px;
      cursor: pointer;
    }}
    .settings-panel {{
      display: none;
      margin-top: 8px;
      padding-top: 8px;
      border-top: 1px dashed rgba(36, 79, 42, 0.16);
    }}
    .settings-panel.open {{
      display: block;
    }}
    .settings-panel label {{
      display: block;
      margin-bottom: 6px;
      font-size: 11px;
      color: var(--muted);
    }}
    .settings-controls {{
      display: flex;
      gap: 6px;
      align-items: center;
    }}
    .slot-select {{
      width: 100%;
      min-width: 0;
      border: 1px solid var(--grid);
      border-radius: 8px;
      padding: 5px 8px;
      font-size: 11px;
      background: white;
      color: var(--ink);
    }}
    .save-button {{
      border: 0;
      background: var(--accent);
      color: white;
      border-radius: 8px;
      padding: 6px 10px;
      font-size: 11px;
      cursor: pointer;
      white-space: nowrap;
    }}
    .save-button:disabled {{
      opacity: 0.55;
      cursor: default;
    }}
    .badge {{
      display: inline-block;
      margin-top: 4px;
      padding: 2px 6px;
      border-radius: 999px;
      background: rgba(36, 79, 42, 0.12);
      font-size: 11px;
    }}
    .blocked-label {{
      display: block;
      color: var(--blocked-ink);
      font-size: 12px;
      font-weight: 600;
    }}
    .empty {{
      color: #8d948d;
      font-size: 12px;
    }}
    @media (max-width: 960px) {{
      header, .content, .index, .toolbar {{
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
      .settings-controls {{
        flex-direction: column;
        align-items: stretch;
      }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>{escape(title)}</h1>
    <p class="subtitle">{escape(subtitle)}</p>
  </header>
  <div class="toolbar">
    <p class="hint">Zmeny delaj pres tlacitko Nastaveni. Nabidka filtruje kolize ucitele, vyuku rocniku a vhodne volne mistnosti.</p>
    <div class="status" id="status"></div>
  </div>
  <div class="index">
    {index_links}
  </div>
  <main class="content">
    {sections}
  </main>
  <script>
{build_page_script()}
  </script>
</body>
</html>
"""


def build_entity_section(
    entity_id: str,
    title: str,
    sessions: list[ScheduledSession],
    card_mode: str,
    unavailable_slot_ids: list[int],
    session_sizes: dict[str, int],
) -> str:
    unavailable_slot_set = set(unavailable_slot_ids)
    grid: dict[tuple[int, int], list[ScheduledSession]] = defaultdict(list)
    for session in sessions:
        grid[(DAY_CODES.index(session.day_code), session.slot_id % SLOTS_PER_DAY)].append(session)

    rows = []
    for day_index, day_code in enumerate(DAY_CODES):
        cells = []
        for block_index, (start, end) in enumerate(STANDARD_BLOCK_TIMES):
            slot_id = day_index * SLOTS_PER_DAY + block_index
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
                cell_html = "".join(
                    build_entry(session, card_mode, session_sizes.get(session.session_id, 0))
                    for session in entries
                )
            elif card_mode == "teacher" and slot_id in unavailable_slot_set:
                cell_html = '<span class="blocked-label">Ucitel zde nema byt dostupny</span>'
            else:
                cell_html = '<div class="empty">No class</div>'
            cell_classes = ["teacher-unavailable"] if card_mode == "teacher" and slot_id in unavailable_slot_set else []
            class_attr = f' class="{" ".join(cell_classes)}"' if cell_classes else ""
            cells.append(f"<td{class_attr}>{cell_html}</td>")
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


def build_entry(session: ScheduledSession, card_mode: str, attendee_count: int) -> str:
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
        f'<div class="entry {kind}" data-session-id="{escape(session.session_id)}">'
        f'<div class="entry-top">'
        f'<div class="entry-title"><strong>{escape(kind_label)}</strong></div>'
        f'<div class="entry-actions"><button class="settings-button" type="button" '
        f'data-settings-toggle="{escape(session.session_id)}">Nastaveni</button></div>'
        f"</div>"
        f"{detail}<br>"
        f"Studentu: {attendee_count}<br>"
        f'<span class="badge">{escape(badge)}</span>'
        f'<div class="settings-panel" id="settings-{escape(session.session_id)}" '
        f'data-settings-panel="{escape(session.session_id)}">'
        f'<label for="week-{escape(session.session_id)}">Tyden vyuky</label>'
        f'<div class="settings-controls">'
        f'<select class="slot-select" id="week-{escape(session.session_id)}" '
        f'data-week-select="{escape(session.session_id)}">'
        f'{build_week_pattern_options(session.week_pattern)}'
        f"</select>"
        f"</div>"
        f'<label for="slot-{escape(session.session_id)}">Presun do jineho slotu</label>'
        f'<div class="settings-controls">'
        f'<select class="slot-select" id="slot-{escape(session.session_id)}" '
        f'data-slot-select="{escape(session.session_id)}">'
        f'<option value="">Nacitam moznosti...</option>'
        f"</select>"
        f"</div>"
        f'<label for="room-{escape(session.session_id)}">Mistnost</label>'
        f'<div class="settings-controls">'
        f'<select class="slot-select" id="room-{escape(session.session_id)}" '
        f'data-room-select="{escape(session.session_id)}">'
        f'<option value="">Nejdriv vyber slot</option>'
        f"</select>"
        f'<button class="save-button" type="button" disabled '
        f'data-save-move="{escape(session.session_id)}">Ulozit</button>'
        f"</div>"
        f"</div>"
        f"</div>"
    )


def build_page_script() -> str:
    return """
const statusNode = document.getElementById("status");
const validSlotsBySession = new Map();
const validRoomsBySelection = new Map();

function setStatus(message, isError = false) {
  if (!statusNode) {
    return;
  }
  statusNode.textContent = message;
  statusNode.style.color = isError ? "#8b2020" : "#244f2a";
}

function slotLabel(slot) {
  return `${slot.day_label} ${slot.start}-${slot.end}`;
}

function cacheKey(sessionId, weekPattern) {
  return `${sessionId}::${weekPattern}`;
}

function getSelectedWeekPattern(sessionId) {
  const weekNode = document.querySelector(`[data-week-select="${sessionId}"]`);
  return weekNode ? weekNode.value : "all";
}

async function fetchValidSlots(sessionId, weekPattern) {
  const key = cacheKey(sessionId, weekPattern);
  if (validSlotsBySession.has(key)) {
    return validSlotsBySession.get(key);
  }
  const response = await fetch(
    `/api/sessions/${encodeURIComponent(sessionId)}/valid-slots?week_pattern=${encodeURIComponent(weekPattern)}`
  );
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || "Nepodarilo se nacist povolene sloty.");
  }
  validSlotsBySession.set(key, payload.valid_slots);
  return payload.valid_slots;
}

async function fetchValidRooms(sessionId, slotKey, weekPattern) {
  const key = `${sessionId}::${slotKey}::${weekPattern}`;
  if (validRoomsBySelection.has(key)) {
    return validRoomsBySelection.get(key);
  }
  const response = await fetch(
    `/api/sessions/${encodeURIComponent(sessionId)}/valid-rooms?slot_key=${encodeURIComponent(slotKey)}&week_pattern=${encodeURIComponent(weekPattern)}`
  );
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || "Nepodarilo se nacist povolene mistnosti.");
  }
  validRoomsBySelection.set(key, payload.valid_rooms);
  return payload.valid_rooms;
}

async function populateSlotOptions(sessionId) {
  const selectNode = document.querySelector(`[data-slot-select="${sessionId}"]`);
  const roomNode = document.querySelector(`[data-room-select="${sessionId}"]`);
  const saveButton = document.querySelector(`[data-save-move="${sessionId}"]`);
  const weekPattern = getSelectedWeekPattern(sessionId);
  if (!selectNode || !roomNode || !saveButton) {
    return;
  }
  selectNode.innerHTML = `<option value="">Nacitam moznosti...</option>`;
  roomNode.innerHTML = `<option value="">Nejdriv vyber slot</option>`;
  saveButton.disabled = true;
  try {
    const slots = await fetchValidSlots(sessionId, weekPattern);
    selectNode.innerHTML = "";
    slots.forEach((slot) => {
      const option = document.createElement("option");
      option.value = slot.slot_key;
      option.textContent = slotLabel(slot);
      selectNode.appendChild(option);
    });
    saveButton.disabled = slots.length === 0;
    if (slots.length === 0) {
      selectNode.innerHTML = `<option value="">Neni kam presunout</option>`;
      setStatus("Pro vybrany blok neni k dispozici zadny volny slot.", true);
    } else {
      await populateRoomOptions(sessionId);
      setStatus("Vyber novy slot, mistnost a potvrd Ulozit.");
    }
  } catch (error) {
    selectNode.innerHTML = `<option value="">Nepodarilo se nacist sloty</option>`;
    setStatus(error.message, true);
  }
}

async function populateRoomOptions(sessionId) {
  const slotNode = document.querySelector(`[data-slot-select="${sessionId}"]`);
  const roomNode = document.querySelector(`[data-room-select="${sessionId}"]`);
  const saveButton = document.querySelector(`[data-save-move="${sessionId}"]`);
  const weekPattern = getSelectedWeekPattern(sessionId);
  if (!slotNode || !roomNode || !saveButton) {
    return;
  }
  if (!slotNode.value) {
    roomNode.innerHTML = `<option value="">Nejdriv vyber slot</option>`;
    saveButton.disabled = true;
    return;
  }
  roomNode.innerHTML = `<option value="">Nacitam mistnosti...</option>`;
  saveButton.disabled = true;
  try {
    const rooms = await fetchValidRooms(sessionId, slotNode.value, weekPattern);
    roomNode.innerHTML = "";
    rooms.forEach((room) => {
      const option = document.createElement("option");
      option.value = room.room_id;
      option.textContent = room.label;
      roomNode.appendChild(option);
    });
    if (rooms.length === 0) {
      roomNode.innerHTML = `<option value="">Neni volna vhodna mistnost</option>`;
      setStatus("Pro vybrany slot neni volna zadna vhodna mistnost.", true);
      saveButton.disabled = true;
      return;
    }
    saveButton.disabled = false;
  } catch (error) {
    roomNode.innerHTML = `<option value="">Nepodarilo se nacist mistnosti</option>`;
    setStatus(error.message, true);
  }
}

function closeAllPanels() {
  document.querySelectorAll("[data-settings-panel]").forEach((panel) => {
    panel.classList.remove("open");
  });
}

document.querySelectorAll("[data-settings-toggle]").forEach((button) => {
  button.addEventListener("click", async () => {
    const sessionId = button.dataset.settingsToggle;
    const panel = document.querySelector(`[data-settings-panel="${sessionId}"]`);
    if (!panel) {
      return;
    }
    const shouldOpen = !panel.classList.contains("open");
    closeAllPanels();
    if (!shouldOpen) {
      return;
    }
    panel.classList.add("open");
    await populateSlotOptions(sessionId);
  });
});

document.querySelectorAll("[data-week-select]").forEach((selectNode) => {
  selectNode.addEventListener("change", async () => {
    await populateSlotOptions(selectNode.dataset.weekSelect);
  });
});

document.querySelectorAll("[data-slot-select]").forEach((selectNode) => {
  selectNode.addEventListener("change", async () => {
    await populateRoomOptions(selectNode.dataset.slotSelect);
  });
});

document.querySelectorAll("[data-save-move]").forEach((button) => {
  button.addEventListener("click", async () => {
    const sessionId = button.dataset.saveMove;
    const selectNode = document.querySelector(`[data-slot-select="${sessionId}"]`);
    const roomNode = document.querySelector(`[data-room-select="${sessionId}"]`);
    const weekPattern = getSelectedWeekPattern(sessionId);
    if (!selectNode || !selectNode.value) {
      setStatus("Vyber cilovy slot.", true);
      return;
    }
    if (!roomNode || !roomNode.value) {
      setStatus("Vyber cilovou mistnost.", true);
      return;
    }
    button.disabled = true;
    setStatus("Ukladam zmenu...");
    try {
      const response = await fetch("/api/move", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          session_id: sessionId,
          slot_key: selectNode.value,
          week_pattern: weekPattern,
          room_id: roomNode.value
        })
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.error || "Zmenu se nepodarilo ulozit.");
      }
      setStatus("Zmena ulozena. Obnovuji zobrazeni...");
      window.location.reload();
    } catch (error) {
      button.disabled = false;
      setStatus(error.message, true);
    }
  });
});
"""


def week_pattern_label(pattern: str) -> str:
    if pattern == "all":
        return "kazdy tyden"
    if pattern == "odd":
        return "liche tydny"
    return "sude tydny"


def build_week_pattern_options(selected_pattern: str) -> str:
    options = [
        ("all", "Kazdy tyden"),
        ("odd", "Liche tydny"),
        ("even", "Sude tydny"),
    ]
    return "".join(
        f'<option value="{value}"{" selected" if value == selected_pattern else ""}>{label}</option>'
        for value, label in options
    )


def format_audience(group_ids: list[str]) -> str:
    if len(group_ids) <= 2:
        return ", ".join(group_ids)
    return f"{len(group_ids)} groups"


def anchor_id(value: str) -> str:
    return value.lower().replace(" ", "-").replace("/", "-")
