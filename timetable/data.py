from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from math import ceil
from random import Random

from timetable.models import (
    Cohort,
    Course,
    DAY_CODES,
    Room,
    STANDARD_BLOCK_TIMES,
    StudyGroup,
    Teacher,
    TIME_BLOCKS,
    UniversityDataset,
    WEEK_PATTERN_ALL,
    WEEK_PATTERN_EVEN,
    WEEK_PATTERN_ODD,
)


@dataclass(frozen=True)
class SubjectTemplate:
    name: str
    practical_feature: str
    practical_group_size: int
    practice_pattern_mode: str = "mixed"


@dataclass(frozen=True)
class ProgramSpec:
    id: str
    name: str
    department: str
    base_size: int
    year_templates: tuple[tuple[SubjectTemplate, ...], ...]


@dataclass(frozen=True)
class DatasetConfig:
    random_seed: int = 17
    program_count: int = 8
    years_per_program: int = 3
    courses_per_year: int = 5
    target_group_size: int = 28
    professors_per_program: int = 5
    instructors_per_program: int = 6


@dataclass
class TeacherBuilder:
    id: str
    name: str
    department: str
    role: str
    subjects: set[str]
    load: float = 0.0

    def to_teacher(
        self,
        unavailable_slot_ids: list[int],
        preferred_day_codes: list[str],
        avoid_single_block_days: bool,
        preferred_max_teaching_days: int,
        absolute_max_teaching_days: int,
    ) -> Teacher:
        return Teacher(
            id=self.id,
            name=self.name,
            department=self.department,
            subjects=sorted(self.subjects),
            unavailable_slot_ids=sorted(unavailable_slot_ids),
            preferred_day_codes=preferred_day_codes,
            avoid_single_block_days=avoid_single_block_days,
            preferred_max_teaching_days=preferred_max_teaching_days,
            absolute_max_teaching_days=absolute_max_teaching_days,
        )


PROGRAM_SPECS: tuple[ProgramSpec, ...] = (
    ProgramSpec(
        id="CS",
        name="Computer Science",
        department="School of Computing",
        base_size=180,
        year_templates=(
            (
                SubjectTemplate("Programming Fundamentals", "computer_lab", 28),
                SubjectTemplate("Discrete Mathematics", "seminar_room", 32),
                SubjectTemplate("Computer Systems Basics", "electronics_lab", 24, "alternate"),
                SubjectTemplate("Database Foundations", "computer_lab", 26),
                SubjectTemplate("Web Engineering Basics", "computer_lab", 26),
            ),
            (
                SubjectTemplate("Algorithms and Complexity", "seminar_room", 30),
                SubjectTemplate("Operating Systems", "computer_lab", 24, "weekly"),
                SubjectTemplate("Network Architectures", "computer_lab", 24),
                SubjectTemplate("Software Design Studio", "project_room", 24, "weekly"),
                SubjectTemplate("Data Structures and Performance", "computer_lab", 24),
            ),
            (
                SubjectTemplate("Distributed Systems", "computer_lab", 24, "weekly"),
                SubjectTemplate("Machine Learning Fundamentals", "computer_lab", 26),
                SubjectTemplate("Applied Information Security", "computer_lab", 24),
                SubjectTemplate("Cloud Platforms", "project_room", 24),
                SubjectTemplate("Capstone Engineering Studio", "project_room", 22, "weekly"),
            ),
        ),
    ),
    ProgramSpec(
        id="DS",
        name="Data Science",
        department="School of Data Systems",
        base_size=165,
        year_templates=(
            (
                SubjectTemplate("Python for Data Analysis", "computer_lab", 26),
                SubjectTemplate("Linear Algebra for Analytics", "seminar_room", 32),
                SubjectTemplate("Probability and Statistics", "seminar_room", 32),
                SubjectTemplate("Data Engineering Basics", "computer_lab", 24),
                SubjectTemplate("Business Communication", "seminar_room", 34, "alternate"),
            ),
            (
                SubjectTemplate("Machine Learning Methods", "computer_lab", 24, "weekly"),
                SubjectTemplate("Data Warehousing", "computer_lab", 24),
                SubjectTemplate("Visualization Studio", "project_room", 24, "weekly"),
                SubjectTemplate("Time Series Analysis", "computer_lab", 24),
                SubjectTemplate("Optimization Models", "seminar_room", 30),
            ),
            (
                SubjectTemplate("Deep Learning Systems", "computer_lab", 22, "weekly"),
                SubjectTemplate("MLOps Platform Engineering", "project_room", 22, "weekly"),
                SubjectTemplate("Streaming Data Pipelines", "computer_lab", 24),
                SubjectTemplate("Responsible AI", "seminar_room", 30),
                SubjectTemplate("Decision Intelligence Studio", "project_room", 24),
            ),
        ),
    ),
    ProgramSpec(
        id="CYB",
        name="Cyber Security",
        department="School of Security Engineering",
        base_size=150,
        year_templates=(
            (
                SubjectTemplate("Security Foundations", "seminar_room", 30),
                SubjectTemplate("Linux Administration", "computer_lab", 24, "weekly"),
                SubjectTemplate("Network Defense Basics", "computer_lab", 24),
                SubjectTemplate("Secure Programming", "computer_lab", 24),
                SubjectTemplate("Cryptography I", "seminar_room", 28),
            ),
            (
                SubjectTemplate("Penetration Testing", "computer_lab", 22, "weekly"),
                SubjectTemplate("Digital Forensics", "computer_lab", 22, "weekly"),
                SubjectTemplate("Identity and Access Management", "seminar_room", 28),
                SubjectTemplate("Cloud Security", "computer_lab", 24),
                SubjectTemplate("Security Operations Center Lab", "computer_lab", 20, "weekly"),
            ),
            (
                SubjectTemplate("Industrial Control Security", "electronics_lab", 20, "weekly"),
                SubjectTemplate("Threat Intelligence", "computer_lab", 22),
                SubjectTemplate("Incident Response Workshop", "project_room", 20, "weekly"),
                SubjectTemplate("Advanced Cryptography", "seminar_room", 26),
                SubjectTemplate("Secure Systems Integration", "computer_lab", 22),
            ),
        ),
    ),
    ProgramSpec(
        id="SWE",
        name="Software Engineering",
        department="School of Software Systems",
        base_size=170,
        year_templates=(
            (
                SubjectTemplate("Object Oriented Programming", "computer_lab", 26),
                SubjectTemplate("Requirements Engineering", "seminar_room", 30),
                SubjectTemplate("Software Testing Basics", "computer_lab", 24),
                SubjectTemplate("User Experience Design", "project_room", 24, "weekly"),
                SubjectTemplate("Version Control and Tooling", "computer_lab", 24, "alternate"),
            ),
            (
                SubjectTemplate("Architecture Patterns", "seminar_room", 28),
                SubjectTemplate("Backend Engineering", "computer_lab", 24, "weekly"),
                SubjectTemplate("Frontend Systems", "computer_lab", 24, "weekly"),
                SubjectTemplate("DevOps Foundations", "computer_lab", 24),
                SubjectTemplate("Quality Engineering Studio", "project_room", 24, "weekly"),
            ),
            (
                SubjectTemplate("Distributed Product Development", "project_room", 22, "weekly"),
                SubjectTemplate("Enterprise Integration", "computer_lab", 24),
                SubjectTemplate("Software Project Management", "seminar_room", 30),
                SubjectTemplate("Cloud Native Applications", "computer_lab", 24),
                SubjectTemplate("Graduation Design Studio", "project_room", 20, "weekly"),
            ),
        ),
    ),
    ProgramSpec(
        id="BAN",
        name="Business Analytics",
        department="School of Management Analytics",
        base_size=140,
        year_templates=(
            (
                SubjectTemplate("Microeconomics for Analysts", "seminar_room", 34),
                SubjectTemplate("Accounting Data Models", "computer_lab", 26),
                SubjectTemplate("Spreadsheet Engineering", "computer_lab", 28),
                SubjectTemplate("Statistics for Business", "seminar_room", 34),
                SubjectTemplate("Process Mapping", "project_room", 28),
            ),
            (
                SubjectTemplate("Managerial Finance Analytics", "seminar_room", 32),
                SubjectTemplate("Predictive Business Models", "computer_lab", 24),
                SubjectTemplate("Supply Chain Planning", "project_room", 26),
                SubjectTemplate("Operations Management", "seminar_room", 30),
                SubjectTemplate("Dashboard Development", "computer_lab", 24, "weekly"),
            ),
            (
                SubjectTemplate("Revenue Management", "seminar_room", 30),
                SubjectTemplate("Strategy Simulation Lab", "project_room", 22, "weekly"),
                SubjectTemplate("Customer Intelligence", "computer_lab", 24),
                SubjectTemplate("Process Mining", "computer_lab", 24),
                SubjectTemplate("Consulting Capstone", "project_room", 24, "weekly"),
            ),
        ),
    ),
    ProgramSpec(
        id="ELE",
        name="Electrical Engineering",
        department="School of Electrical Systems",
        base_size=145,
        year_templates=(
            (
                SubjectTemplate("Circuit Theory", "electronics_lab", 22, "weekly"),
                SubjectTemplate("Mathematics for Engineers", "seminar_room", 32),
                SubjectTemplate("Programming for Embedded Systems", "computer_lab", 24),
                SubjectTemplate("Digital Logic", "electronics_lab", 22, "weekly"),
                SubjectTemplate("Physics of Devices", "electronics_lab", 22),
            ),
            (
                SubjectTemplate("Signals and Systems", "electronics_lab", 22),
                SubjectTemplate("Power Electronics", "electronics_lab", 20, "weekly"),
                SubjectTemplate("Control Engineering", "electronics_lab", 20, "weekly"),
                SubjectTemplate("Measurement Systems", "electronics_lab", 20, "weekly"),
                SubjectTemplate("Industrial Networking", "computer_lab", 24),
            ),
            (
                SubjectTemplate("Smart Grid Platforms", "electronics_lab", 18, "weekly"),
                SubjectTemplate("Robotics Control", "electronics_lab", 18, "weekly"),
                SubjectTemplate("PCB Design Studio", "electronics_lab", 18, "weekly"),
                SubjectTemplate("IoT Integration", "computer_lab", 22),
                SubjectTemplate("Engineering Project Lab", "project_room", 20, "weekly"),
            ),
        ),
    ),
    ProgramSpec(
        id="MEC",
        name="Mechanical Engineering",
        department="School of Mechanical Systems",
        base_size=135,
        year_templates=(
            (
                SubjectTemplate("Engineering Mechanics", "mechanics_lab", 22),
                SubjectTemplate("CAD Foundations", "computer_lab", 24, "weekly"),
                SubjectTemplate("Materials Science", "mechanics_lab", 22),
                SubjectTemplate("Manufacturing Basics", "mechanics_lab", 20, "weekly"),
                SubjectTemplate("Technical Drawing", "project_room", 24, "weekly"),
            ),
            (
                SubjectTemplate("Fluid Mechanics", "mechanics_lab", 20),
                SubjectTemplate("Thermal Engineering", "mechanics_lab", 20),
                SubjectTemplate("Machine Design", "mechanics_lab", 20, "weekly"),
                SubjectTemplate("Manufacturing Automation", "mechanics_lab", 18, "weekly"),
                SubjectTemplate("Simulation for Engineers", "computer_lab", 22),
            ),
            (
                SubjectTemplate("Advanced CAD and PLM", "computer_lab", 22, "weekly"),
                SubjectTemplate("Structural Analysis", "mechanics_lab", 18),
                SubjectTemplate("Industrial Robotics", "mechanics_lab", 18, "weekly"),
                SubjectTemplate("Production Planning Studio", "project_room", 20, "weekly"),
                SubjectTemplate("Mechanical Capstone Lab", "mechanics_lab", 18, "weekly"),
            ),
        ),
    ),
    ProgramSpec(
        id="BIO",
        name="Bioinformatics",
        department="School of Biomedical Computing",
        base_size=120,
        year_templates=(
            (
                SubjectTemplate("Molecular Biology for Computing", "biotech_lab", 22),
                SubjectTemplate("Programming for Life Sciences", "computer_lab", 24),
                SubjectTemplate("Biostatistics", "seminar_room", 28),
                SubjectTemplate("Genomics Data Foundations", "computer_lab", 24),
                SubjectTemplate("Laboratory Safety", "biotech_lab", 20, "weekly"),
            ),
            (
                SubjectTemplate("Sequence Analysis", "computer_lab", 24),
                SubjectTemplate("Biological Databases", "computer_lab", 24),
                SubjectTemplate("Proteomics Methods", "biotech_lab", 20, "weekly"),
                SubjectTemplate("Systems Biology", "biotech_lab", 20),
                SubjectTemplate("Computational Chemistry", "computer_lab", 22),
            ),
            (
                SubjectTemplate("Clinical Data Integration", "computer_lab", 22),
                SubjectTemplate("Medical Imaging Analytics", "computer_lab", 22, "weekly"),
                SubjectTemplate("Laboratory Automation", "biotech_lab", 18, "weekly"),
                SubjectTemplate("Precision Medicine Workshop", "project_room", 20, "weekly"),
                SubjectTemplate("Bioinformatics Capstone", "project_room", 20, "weekly"),
            ),
        ),
    ),
)


FIRST_NAMES = (
    "Adam",
    "Ales",
    "Barbora",
    "Daniel",
    "Dominika",
    "Eva",
    "Filip",
    "Hana",
    "Igor",
    "Jakub",
    "Jana",
    "Jan",
    "Karolina",
    "Klara",
    "Lucie",
    "Martin",
    "Michaela",
    "Milan",
    "Natalie",
    "Ondrej",
    "Pavel",
    "Petra",
    "Roman",
    "Tereza",
    "Tomas",
    "Veronika",
)

LAST_NAMES = (
    "Barta",
    "Blaha",
    "Cerny",
    "Dolezal",
    "Fiala",
    "Horak",
    "Jelinek",
    "Kolar",
    "Kubes",
    "Mach",
    "Marek",
    "Mikula",
    "Navratil",
    "Novak",
    "Pavlik",
    "Prochazka",
    "Ruzicka",
    "Sedlacek",
    "Simek",
    "Svoboda",
    "Urban",
    "Vacek",
    "Valenta",
    "Zeman",
)


def generate_dataset(config: DatasetConfig = DatasetConfig()) -> UniversityDataset:
    random = Random(config.random_seed)
    selected_programs = PROGRAM_SPECS[: config.program_count]

    rooms = build_rooms()
    teacher_builders = create_teacher_builders(config, selected_programs)
    teacher_pools = index_teacher_pools(teacher_builders)

    cohorts: list[Cohort] = []
    study_groups: list[StudyGroup] = []
    courses: list[Course] = []

    for program in selected_programs:
        for year_index in range(config.years_per_program):
            year = year_index + 1
            templates = program.year_templates[year_index][: config.courses_per_year]
            tightest_group_size = min(
                [config.target_group_size]
                + [template.practical_group_size for template in templates]
            )
            cohort = build_cohort(
                program,
                year,
                random,
                max_group_size=tightest_group_size,
            )
            cohorts.append(cohort)
            cohort_groups = build_study_groups(cohort)
            study_groups.extend(cohort_groups)
            for course_index, template in enumerate(templates, start=1):
                course_number = year * 100 + course_index
                course_id = f"{program.id}-Y{year}-{course_index:02d}"
                course_code = f"{program.id}{course_number}"

                lecture_teacher = choose_teacher(
                    teacher_pools[program.id]["professors"],
                    teacher_builders,
                )
                lecture_teacher.subjects.add(course_id)
                lecture_teacher.load += 1.8

                practical_teacher_by_group: dict[str, str] = {}
                practice_pool = (
                    teacher_pools[program.id]["instructors"]
                    + teacher_pools[program.id]["professors"]
                )
                practical_frequency = choose_practical_frequency(template, random)
                practical_weight = 1.0 if practical_frequency == WEEK_PATTERN_ALL else 0.55

                for group in cohort_groups:
                    practical_teacher = choose_teacher(practice_pool, teacher_builders)
                    practical_teacher.subjects.add(course_id)
                    practical_teacher.load += practical_weight
                    practical_teacher_by_group[group.id] = practical_teacher.id

                courses.append(
                    Course(
                        id=course_id,
                        code=course_code,
                        name=template.name,
                        program_id=program.id,
                        program_name=program.name,
                        year=year,
                        cohort_id=cohort.id,
                        student_count=cohort.size,
                        lecture_teacher_id=lecture_teacher.id,
                        practical_teacher_by_group=practical_teacher_by_group,
                        lecture_room_features=["lecture_hall"],
                        practical_room_features=[template.practical_feature],
                        lecture_blocks_per_week=1,
                        practical_frequency=practical_frequency,
                        practical_group_size=template.practical_group_size,
                    )
                )

    teachers = finalize_teachers(list(teacher_builders.values()), random)
    meta = {
        "seed": config.random_seed,
        "programs": [program.name for program in selected_programs],
        "time_blocks": [
            {
                "day_code": block.day_code,
                "day_label": block.day_label,
                "start": block.start,
                "end": block.end,
                "slot_id": block.index,
            }
            for block in TIME_BLOCKS
        ],
        "notes": {
            "lecture_rule": "Every course has one weekly lecture block.",
            "practical_rule": (
                "Most practicals are alternating odd/even weeks. "
                "A smaller subset is every week."
            ),
            "lecture_halls": 8,
            "slots_per_day": len(STANDARD_BLOCK_TIMES),
        },
    }

    return UniversityDataset(
        teachers=teachers,
        rooms=rooms,
        cohorts=cohorts,
        study_groups=study_groups,
        courses=courses,
        meta=meta,
    )


def build_rooms() -> list[Room]:
    rooms: list[Room] = []
    lecture_capacities = [180, 200, 220, 240, 260, 280, 300, 320]
    for index, capacity in enumerate(lecture_capacities, start=1):
        rooms.append(
            Room(
                id=f"LH-{index:02d}",
                name=f"Lecture Hall {index}",
                capacity=capacity,
                building="Central Campus",
                features=["lecture_hall"],
            )
        )

    rooms.extend(
        build_feature_rooms("SR", "Seminar Room", "seminar_room", 14, 30, 42, "North Wing")
    )
    rooms.extend(
        build_feature_rooms("CL", "Computer Lab", "computer_lab", 12, 22, 30, "Digital Center")
    )
    rooms.extend(
        build_feature_rooms("PR", "Project Room", "project_room", 8, 20, 28, "Innovation Hub")
    )
    rooms.extend(
        build_feature_rooms("EL", "Electronics Lab", "electronics_lab", 6, 18, 24, "Engineering Hall")
    )
    rooms.extend(
        build_feature_rooms("ML", "Mechanics Lab", "mechanics_lab", 6, 18, 24, "Mechanical Hall")
    )
    rooms.extend(
        build_feature_rooms("BL", "Biotech Lab", "biotech_lab", 5, 18, 24, "Life Science Center")
    )
    return rooms


def build_feature_rooms(
    prefix: str,
    title: str,
    feature: str,
    count: int,
    min_capacity: int,
    max_capacity: int,
    building: str,
) -> list[Room]:
    spread = max_capacity - min_capacity
    rooms: list[Room] = []
    for index in range(count):
        capacity = min_capacity + (spread * index) // max(count - 1, 1)
        rooms.append(
            Room(
                id=f"{prefix}-{index + 1:02d}",
                name=f"{title} {index + 1}",
                capacity=capacity,
                building=building,
                features=[feature],
            )
        )
    return rooms


def create_teacher_builders(
    config: DatasetConfig,
    selected_programs: tuple[ProgramSpec, ...],
) -> dict[str, TeacherBuilder]:
    builders: dict[str, TeacherBuilder] = {}
    name_cursor = 0
    for program in selected_programs:
        for role, count in (
            ("professor", config.professors_per_program),
            ("instructor", config.instructors_per_program),
        ):
            for serial in range(count):
                first_name = FIRST_NAMES[name_cursor % len(FIRST_NAMES)]
                last_name = LAST_NAMES[(name_cursor * 3 + serial) % len(LAST_NAMES)]
                teacher_id = f"{program.id}-{role[:3].upper()}-{serial + 1:02d}"
                builders[teacher_id] = TeacherBuilder(
                    id=teacher_id,
                    name=f"{first_name} {last_name}",
                    department=program.department,
                    role=role,
                    subjects=set(),
                )
                name_cursor += 1
    return builders


def index_teacher_pools(
    teacher_builders: dict[str, TeacherBuilder],
) -> dict[str, dict[str, list[str]]]:
    pools: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for teacher_id, builder in teacher_builders.items():
        program_id = teacher_id.split("-")[0]
        pools[program_id][f"{builder.role}s"].append(teacher_id)
    return pools


def build_cohort(
    program: ProgramSpec,
    year: int,
    random: Random,
    max_group_size: int,
) -> Cohort:
    drift = random.randint(-10, 12)
    size = max(70, program.base_size - (year - 1) * 14 + drift)
    group_count = ceil(size / max_group_size)
    return Cohort(
        id=f"{program.id}-Y{year}",
        program_id=program.id,
        program_name=program.name,
        year=year,
        size=size,
        group_count=group_count,
    )


def build_study_groups(cohort: Cohort) -> list[StudyGroup]:
    base_size = cohort.size // cohort.group_count
    remainder = cohort.size % cohort.group_count
    groups: list[StudyGroup] = []
    for index in range(cohort.group_count):
        size = base_size + (1 if index < remainder else 0)
        groups.append(
            StudyGroup(
                id=f"{cohort.id}-G{index + 1}",
                cohort_id=cohort.id,
                name=f"{cohort.id} Group {index + 1}",
                size=size,
            )
        )
    return groups


def choose_practical_frequency(template: SubjectTemplate, random: Random) -> str:
    if template.practice_pattern_mode == "weekly":
        return WEEK_PATTERN_ALL
    if template.practice_pattern_mode == "alternate":
        return random.choice([WEEK_PATTERN_ODD, WEEK_PATTERN_EVEN])
    return random.choices(
        [WEEK_PATTERN_ODD, WEEK_PATTERN_EVEN, WEEK_PATTERN_ALL],
        weights=[4, 4, 2],
        k=1,
    )[0]


def choose_teacher(
    pool: list[str],
    teacher_builders: dict[str, TeacherBuilder],
) -> TeacherBuilder:
    teacher_id = min(
        pool,
        key=lambda candidate: (
            teacher_builders[candidate].load,
            len(teacher_builders[candidate].subjects),
            candidate,
        ),
    )
    return teacher_builders[teacher_id]


def finalize_teachers(
    builders: list[TeacherBuilder],
    random: Random,
) -> list[Teacher]:
    teachers: list[Teacher] = []
    all_slot_ids = [block.index for block in TIME_BLOCKS]
    late_slots = [block.index for block in TIME_BLOCKS if block.block_index >= 5]

    for builder in builders:
        unavailable = set()
        base_unavailable = 3 if builder.load >= 10 else 4 if builder.load >= 6 else 5
        while len(unavailable) < base_unavailable:
            unavailable.add(random.choice(all_slot_ids))
        if builder.role == "professor" and random.random() < 0.65:
            unavailable.add(random.choice(late_slots))
        preferred_day_codes = choose_preferred_days(sorted(unavailable), builder, random)
        avoid_single_block_days = builder.load >= 4.0
        preferred_max_teaching_days = 2
        absolute_max_teaching_days = 3
        teachers.append(
            builder.to_teacher(
                sorted(unavailable),
                preferred_day_codes=preferred_day_codes,
                avoid_single_block_days=avoid_single_block_days,
                preferred_max_teaching_days=preferred_max_teaching_days,
                absolute_max_teaching_days=absolute_max_teaching_days,
            )
        )
    return teachers


def choose_preferred_days(
    unavailable_slot_ids: list[int],
    builder: TeacherBuilder,
    random: Random,
) -> list[str]:
    unavailable_per_day = {day_code: 0 for day_code in DAY_CODES}
    for slot_id in unavailable_slot_ids:
        block = TIME_BLOCKS[slot_id]
        unavailable_per_day[block.day_code] += 1

    preferred_day_count = 3 if builder.load >= 7.0 else 2
    ranked_days = sorted(
        DAY_CODES,
        key=lambda day_code: (
            unavailable_per_day[day_code],
            random.random(),
        ),
    )
    return list(ranked_days[:preferred_day_count])
