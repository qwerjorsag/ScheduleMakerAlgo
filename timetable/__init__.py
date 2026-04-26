from timetable.data import DatasetConfig, generate_dataset
from timetable.models import UniversityDataset
from timetable.render import RenderedArtifacts, render_outputs

try:
    from timetable.solver import SolveOptions, solve_timetable
except ModuleNotFoundError as exc:
    if exc.name != "ortools":
        raise
    SolveOptions = None

    def solve_timetable(*args, **kwargs):
        raise ModuleNotFoundError(
            "Missing dependency 'ortools'. Install it with "
            "'python -m pip install -r requirements.txt'."
        ) from exc

__all__ = [
    "DatasetConfig",
    "RenderedArtifacts",
    "SolveOptions",
    "UniversityDataset",
    "generate_dataset",
    "render_outputs",
    "solve_timetable",
]
