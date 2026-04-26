from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from ortools.sat.python import cp_model

from timetable.models import (
    DAY_CODES,
    SLOTS_PER_DAY,
    SESSION_KIND_LECTURE,
    SESSION_KIND_PRACTICAL,
    ScheduleResult,
    ScheduledSession,
    SessionRequest,
    TIME_BLOCKS,
    UniversityDataset,
    WEEK_PATTERN_ALL,
    WEEK_PATTERN_EVEN,
    WEEK_PATTERN_ODD,
)


@dataclass(frozen=True)
class SolveOptions:
    time_limit_seconds: int = 60
    teacher_day_weight: int = 1000
    teacher_excess_day_weight: int = 420
    teacher_single_day_weight: int = 650
    teacher_double_block_day_weight: int = 180
    teacher_nonpreferred_day_weight: int = 140
    group_day_weight: int = 12
    early_block_weight: int = 3
    late_block_weight: int = 8
    random_seed: int = 17
    num_workers: int = 8
    log_search_progress: bool = False


def solve_timetable(
    dataset: UniversityDataset,
    options: SolveOptions = SolveOptions(),
) -> ScheduleResult:
    teachers_by_id = {teacher.id: teacher for teacher in dataset.teachers}
    rooms_by_id = {room.id: room for room in dataset.rooms}

    sessions = build_session_requests(dataset)
    compatible_rooms = {
        session.id: find_compatible_rooms(session, dataset.rooms)
        for session in sessions
    }
    for session_id, room_ids in compatible_rooms.items():
        if not room_ids:
            raise ValueError(f"No compatible room found for session {session_id}.")

    model = cp_model.CpModel()
    placement_vars: dict[tuple[str, int, str], cp_model.IntVar] = {}
    session_placements: dict[str, list[cp_model.IntVar]] = defaultdict(list)
    room_usage_odd: dict[tuple[str, int], list[cp_model.IntVar]] = defaultdict(list)
    room_usage_even: dict[tuple[str, int], list[cp_model.IntVar]] = defaultdict(list)
    teacher_usage_odd: dict[tuple[str, int], list[cp_model.IntVar]] = defaultdict(list)
    teacher_usage_even: dict[tuple[str, int], list[cp_model.IntVar]] = defaultdict(list)
    group_usage_odd: dict[tuple[str, int], list[cp_model.IntVar]] = defaultdict(list)
    group_usage_even: dict[tuple[str, int], list[cp_model.IntVar]] = defaultdict(list)
    teacher_day_pattern_usage: dict[tuple[str, int, str], list[cp_model.IntVar]] = defaultdict(list)
    teacher_day_vars: dict[tuple[str, int], cp_model.IntVar] = {}
    group_day_vars: dict[tuple[str, int], cp_model.IntVar] = {}
    teacher_single_day_vars: dict[tuple[str, int, str], cp_model.IntVar] = {}
    teacher_double_block_day_vars: dict[tuple[str, int, str], cp_model.IntVar] = {}
    teacher_excess_day_vars: dict[str, cp_model.IntVar] = {}
    teacher_nonpreferred_day_penalties: list[cp_model.LinearExpr] = []
    edge_hour_penalties: list[cp_model.LinearExpr] = []

    for session in sessions:
        teacher = teachers_by_id[session.teacher_id]
        unavailable = set(teacher.unavailable_slot_ids)
        for slot in TIME_BLOCKS:
            if slot.index in unavailable:
                continue
            for room_id in compatible_rooms[session.id]:
                var = model.NewBoolVar(f"x_{session.id}_{slot.index}_{room_id}")
                placement_vars[(session.id, slot.index, room_id)] = var
                session_placements[session.id].append(var)

                if session.week_pattern in {WEEK_PATTERN_ALL, WEEK_PATTERN_ODD}:
                    room_usage_odd[(room_id, slot.index)].append(var)
                    teacher_usage_odd[(session.teacher_id, slot.index)].append(var)
                    teacher_day_pattern_usage[
                        (session.teacher_id, slot.day_index, WEEK_PATTERN_ODD)
                    ].append(var)
                    for group_id in session.audience_group_ids:
                        group_usage_odd[(group_id, slot.index)].append(var)
                if session.week_pattern in {WEEK_PATTERN_ALL, WEEK_PATTERN_EVEN}:
                    room_usage_even[(room_id, slot.index)].append(var)
                    teacher_usage_even[(session.teacher_id, slot.index)].append(var)
                    teacher_day_pattern_usage[
                        (session.teacher_id, slot.day_index, WEEK_PATTERN_EVEN)
                    ].append(var)
                    for group_id in session.audience_group_ids:
                        group_usage_even[(group_id, slot.index)].append(var)

                day_key = (session.teacher_id, slot.day_index)
                teacher_day_var = teacher_day_vars.setdefault(
                    day_key,
                    model.NewBoolVar(f"teacher_day_{session.teacher_id}_{slot.day_index}"),
                )
                model.Add(var <= teacher_day_var)

                for group_id in session.audience_group_ids:
                    group_day_key = (group_id, slot.day_index)
                    group_day_var = group_day_vars.setdefault(
                        group_day_key,
                        model.NewBoolVar(f"group_day_{group_id}_{slot.day_index}"),
                    )
                    model.Add(var <= group_day_var)

                if slot.block_index == 0:
                    edge_hour_penalties.append(var * options.early_block_weight)
                elif slot.block_index >= 5:
                    penalty = options.late_block_weight * (slot.block_index - 4)
                    edge_hour_penalties.append(var * penalty)

        if not session_placements[session.id]:
            raise ValueError(f"Session {session.id} has no feasible placements.")
        model.Add(sum(session_placements[session.id]) == 1)

    add_resource_conflicts(model, room_usage_odd)
    add_resource_conflicts(model, room_usage_even)
    add_resource_conflicts(model, teacher_usage_odd)
    add_resource_conflicts(model, teacher_usage_even)
    add_resource_conflicts(model, group_usage_odd)
    add_resource_conflicts(model, group_usage_even)
    add_teacher_short_day_penalties(
        model=model,
        teachers_by_id=teachers_by_id,
        teacher_day_pattern_usage=teacher_day_pattern_usage,
        teacher_single_day_vars=teacher_single_day_vars,
        teacher_double_block_day_vars=teacher_double_block_day_vars,
    )
    for (teacher_id, day_index), day_var in teacher_day_vars.items():
        if DAY_CODES[day_index] not in teachers_by_id[teacher_id].preferred_day_codes:
            teacher_nonpreferred_day_penalties.append(
                day_var * options.teacher_nonpreferred_day_weight
            )
    add_teacher_day_limits(
        model=model,
        teachers_by_id=teachers_by_id,
        teacher_day_vars=teacher_day_vars,
        teacher_excess_day_vars=teacher_excess_day_vars,
    )

    teacher_day_expr = sum(teacher_day_vars.values())
    teacher_excess_day_expr = sum(teacher_excess_day_vars.values())
    teacher_single_day_expr = sum(teacher_single_day_vars.values())
    teacher_double_block_day_expr = sum(teacher_double_block_day_vars.values())
    teacher_nonpreferred_day_expr = sum(teacher_nonpreferred_day_penalties)
    group_day_expr = sum(group_day_vars.values())
    edge_hour_expr = sum(edge_hour_penalties)

    stage_one_solver = build_solver(options, max(stage_one_time_limit(options.time_limit_seconds), 1))
    model.Minimize(
        teacher_day_expr * options.teacher_day_weight
        + group_day_expr * options.group_day_weight
    )
    status = stage_one_solver.Solve(model)
    if status not in {cp_model.OPTIMAL, cp_model.FEASIBLE}:
        if status == cp_model.UNKNOWN:
            raise RuntimeError(
                "Solver hit the time limit before finding the first feasible timetable. "
                "Increase --time-limit and try again."
            )
        raise RuntimeError(
            f"No feasible timetable found. Solver status: {stage_one_solver.StatusName(status)}"
        )

    best_teacher_days = round(stage_one_solver.Value(teacher_day_expr))
    model.Add(teacher_day_expr == best_teacher_days)
    add_true_solution_hints(
        model,
        stage_one_solver,
        placement_vars.values(),
        teacher_day_vars.values(),
        group_day_vars.values(),
        teacher_excess_day_vars.values(),
        teacher_single_day_vars.values(),
        teacher_double_block_day_vars.values(),
    )

    stage_two_solver = build_solver(options, max(stage_two_time_limit(options.time_limit_seconds), 1))
    model.Minimize(
        teacher_excess_day_expr * options.teacher_excess_day_weight
        + teacher_single_day_expr * options.teacher_single_day_weight
        + teacher_double_block_day_expr * options.teacher_double_block_day_weight
        + teacher_nonpreferred_day_expr
        + group_day_expr * options.group_day_weight
        + edge_hour_expr
    )
    stage_two_status = stage_two_solver.Solve(model)
    if stage_two_status in {cp_model.OPTIMAL, cp_model.FEASIBLE}:
        solver = stage_two_solver
        status = stage_two_status
    else:
        solver = stage_one_solver
        status = status

    sessions_by_id = {session.id: session for session in sessions}
    scheduled: list[ScheduledSession] = []
    for (session_id, slot_id, room_id), var in placement_vars.items():
        if not solver.BooleanValue(var):
            continue
        request = sessions_by_id[session_id]
        room = rooms_by_id[room_id]
        slot = TIME_BLOCKS[slot_id]
        scheduled.append(
            ScheduledSession(
                session_id=request.id,
                course_id=request.course_id,
                course_code=request.course_code,
                course_name=request.course_name,
                teacher_id=request.teacher_id,
                teacher_name=request.teacher_name,
                cohort_id=request.cohort_id,
                audience_group_ids=request.audience_group_ids,
                session_kind=request.session_kind,
                week_pattern=request.week_pattern,
                room_id=room.id,
                room_name=room.name,
                day_code=slot.day_code,
                day_label=slot.day_label,
                start=slot.start,
                end=slot.end,
                slot_id=slot_id,
                display_label=request.display_label,
            )
        )

    scheduled.sort(
        key=lambda session: (
            DAY_CODES.index(session.day_code),
            session.slot_id % SLOTS_PER_DAY,
            session.teacher_name,
            session.course_code,
            session.room_name,
        )
    )

    teacher_days = sum(solver.BooleanValue(var) for var in teacher_day_vars.values())
    teacher_excess_days = sum(solver.Value(var) for var in teacher_excess_day_vars.values())
    teacher_single_days = sum(
        solver.BooleanValue(var) for var in teacher_single_day_vars.values()
    )
    teacher_double_block_days = sum(
        solver.BooleanValue(var) for var in teacher_double_block_day_vars.values()
    )
    group_days = sum(solver.BooleanValue(var) for var in group_day_vars.values())
    late_sessions = sum(1 for session in scheduled if TIME_BLOCKS[session.slot_id].block_index >= 5)
    edge_hour_penalty_value = 0
    for session in scheduled:
        block_index = TIME_BLOCKS[session.slot_id].block_index
        if block_index == 0:
            edge_hour_penalty_value += options.early_block_weight
        elif block_index >= 5:
            edge_hour_penalty_value += options.late_block_weight * (block_index - 4)
    objective_value = (
        teacher_days * options.teacher_day_weight
        + teacher_excess_days * options.teacher_excess_day_weight
        + teacher_single_days * options.teacher_single_day_weight
        + teacher_double_block_days * options.teacher_double_block_day_weight
        + sum(
            options.teacher_nonpreferred_day_weight
            for (teacher_id, day_index), day_var in teacher_day_vars.items()
            if solver.BooleanValue(day_var)
            and DAY_CODES[day_index] not in teachers_by_id[teacher_id].preferred_day_codes
        )
        + group_days * options.group_day_weight
        + edge_hour_penalty_value
    )

    return ScheduleResult(
        sessions=scheduled,
        objective_value=objective_value,
        teacher_days=teacher_days,
        teacher_single_days=teacher_single_days,
        teacher_double_block_days=teacher_double_block_days,
        group_days=group_days,
        late_sessions=late_sessions,
        status=solver.StatusName(status),
    )


def build_session_requests(dataset: UniversityDataset) -> list[SessionRequest]:
    teachers_by_id = {teacher.id: teacher for teacher in dataset.teachers}
    groups_by_cohort: dict[str, list] = defaultdict(list)
    groups_by_id = {group.id: group for group in dataset.study_groups}

    for group in dataset.study_groups:
        groups_by_cohort[group.cohort_id].append(group)

    requests: list[SessionRequest] = []
    for course in dataset.courses:
        lecture_teacher = teachers_by_id[course.lecture_teacher_id]
        cohort_groups = groups_by_cohort[course.cohort_id]
        requests.append(
            SessionRequest(
                id=f"{course.id}-LEC",
                course_id=course.id,
                course_code=course.code,
                course_name=course.name,
                teacher_id=lecture_teacher.id,
                teacher_name=lecture_teacher.name,
                cohort_id=course.cohort_id,
                audience_group_ids=[group.id for group in cohort_groups],
                session_kind=SESSION_KIND_LECTURE,
                week_pattern=WEEK_PATTERN_ALL,
                allowed_room_features=course.lecture_room_features,
                min_capacity=course.student_count,
                display_label=f"{course.code} lecture",
            )
        )

        for group in cohort_groups:
            practical_teacher_id = course.practical_teacher_by_group[group.id]
            practical_teacher = teachers_by_id[practical_teacher_id]
            requests.append(
                SessionRequest(
                    id=f"{course.id}-PR-{group.id}",
                    course_id=course.id,
                    course_code=course.code,
                    course_name=course.name,
                    teacher_id=practical_teacher.id,
                    teacher_name=practical_teacher.name,
                    cohort_id=course.cohort_id,
                    audience_group_ids=[group.id],
                    session_kind=SESSION_KIND_PRACTICAL,
                    week_pattern=course.practical_frequency,
                    allowed_room_features=course.practical_room_features,
                    min_capacity=groups_by_id[group.id].size,
                    display_label=f"{course.code} practical {group.name}",
                )
            )
    return requests


def find_compatible_rooms(session: SessionRequest, rooms: list) -> list[str]:
    compatible: list[str] = []
    required_features = set(session.allowed_room_features)
    for room in rooms:
        if room.capacity < session.min_capacity:
            continue
        if not required_features.issubset(set(room.features)):
            continue
        compatible.append(room.id)
    return compatible


def add_resource_conflicts(
    model: cp_model.CpModel,
    usage_index: dict[tuple[str, int], list[cp_model.IntVar]],
) -> None:
    for placements in usage_index.values():
        if len(placements) > 1:
            model.Add(sum(placements) <= 1)


def add_teacher_short_day_penalties(
    model: cp_model.CpModel,
    teachers_by_id: dict[str, object],
    teacher_day_pattern_usage: dict[tuple[str, int, str], list[cp_model.IntVar]],
    teacher_single_day_vars: dict[tuple[str, int, str], cp_model.IntVar],
    teacher_double_block_day_vars: dict[tuple[str, int, str], cp_model.IntVar],
) -> None:
    for key, placements in teacher_day_pattern_usage.items():
        load_var = model.NewIntVar(0, SLOTS_PER_DAY, f"teacher_load_{key[0]}_{key[1]}_{key[2]}")
        model.Add(load_var == sum(placements))

        single_day_var = model.NewBoolVar(f"teacher_single_day_{key[0]}_{key[1]}_{key[2]}")
        model.Add(load_var == 1).OnlyEnforceIf(single_day_var)
        model.Add(load_var != 1).OnlyEnforceIf(single_day_var.Not())
        if teachers_by_id[key[0]].avoid_single_block_days:
            model.Add(load_var != 1)
        teacher_single_day_vars[key] = single_day_var

        double_block_day_var = model.NewBoolVar(
            f"teacher_double_block_day_{key[0]}_{key[1]}_{key[2]}"
        )
        model.Add(load_var == 2).OnlyEnforceIf(double_block_day_var)
        model.Add(load_var != 2).OnlyEnforceIf(double_block_day_var.Not())
        teacher_double_block_day_vars[key] = double_block_day_var


def add_teacher_day_limits(
    model: cp_model.CpModel,
    teachers_by_id: dict[str, object],
    teacher_day_vars: dict[tuple[str, int], cp_model.IntVar],
    teacher_excess_day_vars: dict[str, cp_model.IntVar],
) -> None:
    teacher_days_by_teacher: dict[str, list[cp_model.IntVar]] = defaultdict(list)
    for (teacher_id, _day_index), day_var in teacher_day_vars.items():
        teacher_days_by_teacher[teacher_id].append(day_var)

    for teacher_id, day_vars in teacher_days_by_teacher.items():
        teacher = teachers_by_id[teacher_id]
        total_days = model.NewIntVar(
            0,
            len(DAY_CODES),
            f"teacher_total_days_{teacher_id}",
        )
        model.Add(total_days == sum(day_vars))
        model.Add(total_days <= teacher.absolute_max_teaching_days)

        max_excess = max(0, teacher.absolute_max_teaching_days - teacher.preferred_max_teaching_days)
        excess_var = model.NewIntVar(0, max_excess, f"teacher_excess_days_{teacher_id}")
        model.Add(excess_var >= total_days - teacher.preferred_max_teaching_days)
        model.Add(excess_var <= total_days)
        teacher_excess_day_vars[teacher_id] = excess_var


def build_solver(options: SolveOptions, time_limit_seconds: int) -> cp_model.CpSolver:
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_seconds
    solver.parameters.num_search_workers = options.num_workers
    solver.parameters.random_seed = options.random_seed
    solver.parameters.log_search_progress = options.log_search_progress
    solver.parameters.cp_model_presolve = True
    return solver


def stage_one_time_limit(total_seconds: int) -> int:
    if total_seconds <= 2:
        return 1
    return max(1, min(total_seconds - 1, int(total_seconds * 0.85)))


def stage_two_time_limit(total_seconds: int) -> int:
    if total_seconds <= 2:
        return 1
    return max(1, total_seconds - stage_one_time_limit(total_seconds))


def add_true_solution_hints(
    model: cp_model.CpModel,
    solver: cp_model.CpSolver,
    *var_groups,
) -> None:
    for var_group in var_groups:
        for var in var_group:
            if solver.BooleanValue(var):
                model.AddHint(var, 1)
