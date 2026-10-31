# Schedule Maker Algorithm

A standalone school timetable optimizer. It reads school data from separate JSON files, builds lecture and practical sessions, and assigns every session a weekday, time block, and compatible room. The optimizer uses Google OR-Tools CP-SAT.

## What the program does

For every course, the solver creates one weekly lecture for the whole cohort and a practical session for each study group. Practical sessions can run every week (`all`) or alternate between odd and even weeks (`odd`, `even`). It searches for a timetable that satisfies hard constraints and then improves soft preferences.

Hard constraints include:

- A room must have all requested features and enough capacity.
- A room cannot host overlapping sessions.
- A teacher cannot teach overlapping sessions or during an unavailable time block.
- A study group cannot attend overlapping sessions.
- A teacher cannot exceed their absolute maximum teaching days.

The solver also tries to respect preferred teaching days, preferred weekly teaching-day limits, shorter teacher days, and earlier time blocks. These are optimization preferences; the exact result can vary with solver time and machine resources.

## Tuning optimization settings

The solver's adjustable settings are defined by `SolveOptions` in `timetable/solver.py`. `algorithm.py` currently sets only the time limit, so edit its `SolveOptions(...)` call to customize the other values for a particular school. For example:

```python
result = solve_timetable(
    dataset,
    SolveOptions(
        time_limit_seconds=args.time_limit,
        teacher_day_weight=1000,
        teacher_excess_day_weight=420,
        teacher_single_day_weight=650,
        teacher_double_block_day_weight=180,
        teacher_nonpreferred_day_weight=140,
        group_day_weight=12,
        early_block_weight=3,
        late_block_weight=8,
        random_seed=17,
        num_workers=8,
        log_search_progress=False,
    ),
)
```

Weights are relative penalties: increasing one makes the solver prioritize avoiding that outcome more strongly compared with outcomes carrying lower weights. They do not guarantee a preference if the constraints or other weighted preferences make it impractical. Start with small changes to one or two weights, generate a schedule, and compare the result and `objective_value` before making further changes. An objective value is useful when comparing runs with the same data and weights; it is not directly comparable after changing weights.

| Setting | Default | Effect |
| --- | ---: | --- |
| `teacher_day_weight` | 1000 | Penalizes each day on which a teacher has at least one session. Increase to concentrate each teacher's sessions into fewer weekdays. |
| `teacher_excess_day_weight` | 420 | Penalizes teaching days above `preferred_max_teaching_days` in `teachers.json`. This is a soft preference; the absolute limit remains hard. |
| `teacher_single_day_weight` | 650 | Penalizes a teacher having exactly one session on a weekday. |
| `teacher_double_block_day_weight` | 180 | Penalizes a teacher having exactly two sessions on a weekday. |
| `teacher_nonpreferred_day_weight` | 140 | Penalizes assigning a session on a weekday absent from that teacher's `preferred_day_codes`. |
| `group_day_weight` | 12 | Penalizes each weekday on which a study group has classes. Increase to favor fewer school days for groups. |
| `early_block_weight` | 3 | Penalizes the first time block. Set to `0` if early starts should carry no penalty; raise it to discourage them. |
| `late_block_weight` | 8 | Penalizes blocks after the fifth block, with a larger penalty for each later block. Increase to avoid late classes. |
| `time_limit_seconds` | 60 in `SolveOptions` | Solver time budget. The command-line script overrides this with `--time-limit` and defaults to 300 seconds. More time gives the solver more opportunity to find and improve a solution. |
| `random_seed` | 17 | Seed used by CP-SAT. It can affect search order and the schedule found. Keep it fixed for more repeatable runs with the same solver version and machine setup. |
| `num_workers` | 8 | Number of CP-SAT search workers. More workers may improve search speed on a machine with available CPU cores, but consume more resources and can make outcomes less repeatable. |
| `log_search_progress` | `false` | Set to `true` to print CP-SAT search diagnostics to the terminal. |

Teacher record fields also affect scheduling. `preferred_day_codes` and `preferred_max_teaching_days` feed soft penalties; `unavailable_slot_ids`, `avoid_single_block_days`, and `absolute_max_teaching_days` impose hard restrictions. A hard restriction can make the problem infeasible, regardless of preference weights. Relax it in the relevant teacher record only if the school rules allow that change.

The solver optimizes in two stages. First it emphasizes the number of teacher days and group days. Then it keeps the best first-stage value and optimizes the remaining teacher-day preferences and time-of-day penalties. Therefore, weights are most meaningful within their stage; a very large second-stage weight cannot override a better first-stage objective. If a school needs to change that priority between objectives, the optimization logic in `timetable/solver.py` must also be adjusted.

## Requirements

- Python 3.12 or newer
- [uv](https://docs.astral.sh/uv/) (recommended)

## Install and run

Open a terminal in the repository directory and run:

```powershell
uv sync
uv run python algorithm.py
```

The default time limit is 300 seconds. Set a different limit in seconds with:

```powershell
uv run python algorithm.py --time-limit 600
```

The program reads the JSON inputs from `School parametrs/` relative to `algorithm.py`, regardless of the terminal's current directory. On success, it writes `schedule.json` to the project root. This generated output is ignored by Git.

To install without uv:

```powershell
python -m pip install -r requirements.txt
python algorithm.py --time-limit 300
```

## Project layout

```text
algorithm.py                 Command-line entry point
timetable/models.py          School data models and JSON loading/saving
timetable/solver.py          Session creation and CP-SAT optimization
School parametrs/
  courses.json               Courses and course-to-teacher assignments
  study_groups.json          Student groups
  cohorts.json               Program-year cohorts
  rooms.json                 Rooms, capacities, and features
  teachers.json              Teachers, availability, and preferences
  meta.json                  School metadata and time blocks
schedule.json                Generated timetable (created when run; Git ignored)
```

`School parametrs` retains this spelling for compatibility with the current project. Keep the directory name and JSON filenames unchanged unless you also update the loader in `timetable/models.py`.

## School data files

All files must be valid UTF-8 JSON. The data is split by entity so a school can update one category without editing one large dataset. IDs are the links between files and must be unique within their category.

### `teachers.json`

An array of teacher records. Each teacher has:

- `id`, `name`, `department`
- `subjects`: course IDs associated with the teacher
- `unavailable_slot_ids`: numeric slot IDs when the teacher cannot teach
- `preferred_day_codes`: preferred weekdays, using `MON`, `TUE`, `WED`, `THU`, `FRI`
- `avoid_single_block_days`: whether a day with only one session is forbidden
- `preferred_max_teaching_days`: soft preferred weekly limit
- `absolute_max_teaching_days`: hard weekly limit

Example:

```json
{
  "id": "CS-PRO-01",
  "name": "Alex Novak",
  "department": "School of Computing",
  "subjects": ["CS-Y1-01"],
  "unavailable_slot_ids": [4, 5],
  "preferred_day_codes": ["MON", "WED"],
  "avoid_single_block_days": false,
  "preferred_max_teaching_days": 2,
  "absolute_max_teaching_days": 3
}
```

Slot IDs correspond to the ordering in `meta.json`'s `time_blocks` array. In the supplied data, IDs 0–6 are Monday, 7–13 Tuesday, and so on.

### `rooms.json`

An array of rooms. Each room has `id`, `name`, integer `capacity`, `building`, and a `features` array. A room is eligible only if its capacity meets the session size and its features contain every feature requested by the course.

### `cohorts.json`

An array describing a program year, with `id`, `program_id`, `program_name`, `year`, total `size`, and `group_count`. Every cohort referenced by a course or study group must exist. Cohort size should match the sum of its study group sizes.

### `study_groups.json`

An array of practical groups, each with `id`, `cohort_id`, `name`, and `size`. Every group must reference an existing cohort. Courses use these group IDs to assign practical teachers.

### `courses.json`

An array of courses. Each course includes:

- identity and display fields: `id`, `code`, `name`
- program fields: `program_id`, `program_name`, `year`
- `cohort_id` and total `student_count`
- `lecture_teacher_id`: an existing teacher ID
- `practical_teacher_by_group`: map of every applicable study group ID to an existing teacher ID
- `lecture_room_features` and `practical_room_features`
- `lecture_blocks_per_week` (currently one lecture is generated by the solver)
- `practical_frequency`: `all`, `odd`, or `even`
- `practical_group_size`

Example:

```json
{
  "id": "CS-Y1-01",
  "code": "CS101",
  "name": "Programming Fundamentals",
  "program_id": "CS",
  "program_name": "Computer Science",
  "year": 1,
  "cohort_id": "CS-Y1",
  "student_count": 186,
  "lecture_teacher_id": "CS-PRO-01",
  "practical_teacher_by_group": {
    "CS-Y1-G1": "CS-INS-01"
  },
  "lecture_room_features": ["lecture_hall"],
  "practical_room_features": ["computer_lab"],
  "lecture_blocks_per_week": 1,
  "practical_frequency": "even",
  "practical_group_size": 28
}
```

For each course, `practical_teacher_by_group` must include every study group belonging to the course's cohort. Room feature strings must match the values in `rooms.json` exactly.

### `meta.json`

Contains general metadata and `time_blocks`, an ordered array of available blocks. Each block has a `day_code`, localized `day_label`, `start`, `end`, and `slot_id`. The current solver is built around five weekdays and seven blocks per day (35 slots total), matching the supplied data. The time blocks in metadata must remain consistent with the weekday and time-block constants in `timetable/models.py`; editing metadata alone does not currently redefine the solver's calendar.

## Output format

`schedule.json` contains a `sessions` array and summary fields. Each session records the course, teacher, audience groups, session type, week pattern, room, weekday, start/end time, slot ID, and display label. Summary fields include solver status, objective value, teacher teaching days, teacher short days, group days, and late sessions.

`FEASIBLE` means a valid timetable was found within the time limit; the solver may not have finished improving it. `OPTIMAL` means it proved the best objective value. If the solver cannot find a feasible timetable within the time limit, it reports an error instead of writing a new successful schedule.

## Troubleshooting

- **Missing JSON file:** confirm all six expected files are present in `School parametrs/`.
- **Unknown teacher/group/cohort ID:** check cross-file IDs and spelling, including capitalization.
- **No compatible room:** make sure at least one room has the requested features and sufficient capacity for each lecture and practical.
- **No feasible timetable before timeout:** increase `--time-limit`; also check teacher availability, room capacity, and conflicting assignments.
- **JSON parse or missing field error:** validate JSON syntax and required fields against the examples and existing records.

## License

No license is currently specified. Add a `LICENSE` file before granting reuse or redistribution rights.
