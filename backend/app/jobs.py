"""Bounded, in-memory generation queue for the local studio."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from threading import Event, Lock
from time import monotonic
from uuid import uuid4
import logging

from .brazilian import SpeechCancelled
from .tts import get_engine


@dataclass
class Job:
    id: str
    status: str = 'queued'
    completed: int = 0
    total: int = 0
    error: str | None = None
    audio: bytes | None = None
    created: float = field(default_factory=monotonic)
    cancel: Event = field(default_factory=Event)

    def public(self):
        return {'id': self.id, 'status': self.status, 'completed': self.completed,
                'total': self.total, 'error': self.error}


class JobQueue:
    def __init__(self):
        self.jobs = {}
        self.lock = Lock()
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='voxarcana')

    def submit(self, payload):
        with self.lock:
            # Bound queued work and retained audio, without expiring an active job.
            finished = [job for job in self.jobs.values()
                        if job.status in {'done', 'error', 'cancelled'}]
            for job in finished:
                if monotonic() - job.created > 3600 or len(self.jobs) >= 10:
                    self.jobs.pop(job.id, None)
            if sum(job.status in {'queued', 'running', 'cancelling'} for job in self.jobs.values()) >= 3:
                raise ValueError('Já há três narrações na fila. Aguarde ou cancele uma delas.')
            job = Job(id=str(uuid4()))
            self.jobs[job.id] = job
            self.pool.submit(self._run, job, payload)
            return job

    def _run(self, job, payload):
        def progress(completed, total):
            with self.lock:
                job.completed, job.total = completed, total
        try:
            with self.lock:
                if job.cancel.is_set():
                    job.status = 'cancelled'
                    return
                job.status = 'running'
            audio = get_engine().synthesize(**payload, progress=progress,
                                            cancelled=job.cancel.is_set)
            with self.lock:
                if job.cancel.is_set():
                    job.status = 'cancelled'
                else:
                    job.audio, job.status = audio, 'done'
        except SpeechCancelled:
            with self.lock:
                job.status = 'cancelled'
        except Exception as error:
            logging.getLogger(__name__).exception('Falha na narração %s', job.id)
            with self.lock:
                job.error = str(error)
                job.status = 'error'

    def snapshot(self, job_id):
        with self.lock:
            job = self.jobs.get(job_id)
            return job.public() if job else None

    def cancel_job(self, job_id):
        with self.lock:
            job = self.jobs.get(job_id)
            if job and job.status in {'queued', 'running', 'cancelling'}:
                job.cancel.set()
                job.status = 'cancelling'
            return job.public() if job else None


queue = JobQueue()
