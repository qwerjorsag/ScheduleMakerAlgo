# Schedule Maker Algorithm

Standalone school timetable optimizer. It reads atomic school data from `School parametrs/`, solves the timetable with OR-Tools CP-SAT, and writes `schedule.json` in the project root.

## Requirements

- Python 3.12 or newer
- [uv](https://docs.astral.sh/uv/)

## Run

```powershell
uv sync
uv run python algorithm.py
```

Increase the solver time limit (seconds) when needed:

```powershell
uv run python algorithm.py --time-limit 600
```

## School data

Edit the JSON files in `School parametrs/`:

- `courses.json` — courses and teacher assignments
- `study_groups.json` — student groups
- `cohorts.json` — program year cohorts
- `rooms.json` — rooms and their capacities/features
- `teachers.json` — teacher availability and preferences
- `meta.json` — school metadata and time blocks

The IDs referenced between files must match. The solver writes the resulting sessions and summary metrics to `schedule.json`.

## Without uv

```powershell
python -m pip install -r requirements.txt
python algorithm.py
```
