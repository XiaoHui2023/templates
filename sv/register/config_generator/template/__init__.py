from .models import Template
from pathlib import Path

def get_path(name: str) -> str:
    return (Path(__file__).parent / Path(name).with_suffix(".j2"))
