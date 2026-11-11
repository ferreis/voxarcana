"""Persistent project names. Existing casting belongs to the default project."""
import json
from pathlib import Path
from threading import RLock
from uuid import uuid4

PROJECT_FILE = Path(__file__).resolve().parents[1] / 'voices/projects.json'
DEFAULT_PROJECT = {'id': 'default', 'name': 'Projeto inicial'}
_lock = RLock()


def list_projects():
    with _lock:
        records = json.loads(PROJECT_FILE.read_text()) if PROJECT_FILE.exists() else []
        return [DEFAULT_PROJECT, *records]


def create_project(name):
    with _lock:
        records = list_projects()[1:]
        if any(project['name'].casefold() == name.casefold() for project in list_projects()):
            raise ValueError('Já existe um projeto com esse nome.')
        # Freeze legacy casting before synthesis in another project can update cast.json.
        from .characters import list_characters
        list_characters([])
        project = {'id': str(uuid4()), 'name': name}
        PROJECT_FILE.parent.mkdir(parents=True, exist_ok=True)
        temporary = PROJECT_FILE.with_suffix(f'.{uuid4()}.tmp')
        temporary.write_text(json.dumps([*records, project], ensure_ascii=False, indent=2))
        temporary.replace(PROJECT_FILE)
        return project


def require_project(project_id):
    if not any(project['id'] == project_id for project in list_projects()):
        raise LookupError('Projeto não encontrado.')
