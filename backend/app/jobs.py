"""Bounded, in-memory generation queue for the local studio."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from threading import Event, Lock
from time import monotonic
from uuid import uuid4
import logging
import copy

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
    stage: str = 'queued'
    scene: dict | None = None
    speaker: str | None = None
    delivery: str | None = None
    analysis_percent: int = 0
    analysis_events: list[str] = field(default_factory=list)
    review_scene: object | None = None
    review_payload: dict | None = None
    created: float = field(default_factory=monotonic)
    cancel: Event = field(default_factory=Event)

    def public(self):
        return {'id': self.id, 'status': self.status, 'completed': self.completed,
                'total': self.total, 'error': self.error, 'stage': self.stage,
                'analysis_percent': self.analysis_percent, 'analysis_events': list(self.analysis_events),
                'source_text': self.review_payload.get('text') if self.review_payload else None,
                'scene': self.scene, 'speaker': self.speaker, 'delivery': self.delivery}


class JobQueue:
    def __init__(self):
        self.jobs = {}
        self.lock = Lock()
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='voxarcana')

    def submit(self, payload):
        with self.lock:
            # Bound queued work and retained audio, without expiring an active job.
            finished = [job for job in self.jobs.values()
                        if job.status in {'done', 'error', 'cancelled', 'review'}]
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
        def on_scene(scene):
            with self.lock:
                job.scene = scene
        def on_analysis(percent, message):
            with self.lock:
                job.analysis_percent = max(job.analysis_percent, min(100, percent))
                if not job.analysis_events or job.analysis_events[-1] != message:
                    job.analysis_events = (job.analysis_events + [message])[-24:]
        def on_unit(speaker, delivery):
            with self.lock:
                job.speaker, job.delivery = speaker, delivery
        def on_stage(stage):
            with self.lock:
                job.stage = stage
        try:
            with self.lock:
                if job.cancel.is_set():
                    job.status = 'cancelled'
                    return
                job.status = 'running'
            payload = dict(payload)
            review = payload.pop('review', False)
            if review:
                from .scene import get_reader
                on_stage('analyzing')
                scene = get_reader().analyze(payload['text'], job.cancel.is_set, on_progress=on_analysis)
                from .characters import apply_saved
                from .brazilian import voice_catalog
                scene = apply_saved(scene, payload['voice'], voice_catalog())
                with self.lock:
                    if job.cancel.is_set():
                        job.status = 'cancelled'
                        return
                    job.review_scene = scene
                    job.review_payload = payload
                    job.scene = scene.public()
                    job.status = 'review'
                    job.stage = 'review'
                # A análise nunca inicia a síntese, mesmo com elenco salvo ou só narração.
                return
            callbacks = {'on_scene': on_scene, 'on_unit': on_unit, 'on_stage': on_stage, 'on_analysis': on_analysis} if payload.get('automatic') else {}
            audio = get_engine().synthesize(**payload, progress=progress,
                                            cancelled=job.cancel.is_set, **callbacks)
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

    def perform_review(self, job_id, lines, narrator_voice, style, catalog, speed=None):
        from .scene import identity, NARRATOR
        with self.lock:
            job = self.jobs.get(job_id)
            if job is None:
                raise LookupError('Análise não encontrada. Analise o texto novamente.')
            if job.status not in {'review', 'done'} or job.review_scene is None or job.review_payload is None:
                raise ValueError('Essa análise não está disponível para revisar ou gerar novamente.')
            if sum(j.status in {'queued', 'running', 'cancelling'} for j in self.jobs.values()) >= 3:
                raise ValueError('A fila está cheia. Aguarde antes de gerar.')
            voices = {v['id']: v for v in catalog}
            narrator = voices.get(narrator_voice)
            if not narrator or narrator.get('role') == 'character':
                raise ValueError('Escolha uma voz válida de narrador.')
            scene = copy.deepcopy(job.review_scene)
            expected = {s.id for s in scene.spans if s.kind == 'dialogue' and s.text}
            if len(lines) != len({line.id for line in lines}) or {line.id for line in lines} != expected:
                raise ValueError('Revise todas as falas da análise, sem adicionar ou remover trechos.')
            indexed = {line.id: line for line in lines}
            for span in scene.spans:
                if span.id not in indexed:
                    continue
                line = indexed[span.id]
                voice = voices.get(line.voice_id)
                if not voice or voice['id'] == narrator_voice or voice.get('role', 'both') not in {'character', 'both'}:
                    raise ValueError('Cada personagem precisa de outra voz, classificada como Personagem ou Ambos.')
                if identity(line.speaker) == identity(NARRATOR):
                    raise ValueError('O nome Narrador é reservado à narração.')
                span.speaker = line.speaker
                span.gender = line.gender
                span.voice_kind = voice.get('kind', 'human')
                span.voice_id = line.voice_id
                span.voice_override = line.voice_id
            from .characters import remember_review
            remember_review(job.review_scene, scene)
            payload = {**job.review_payload, 'voice': narrator_voice, 'style': style,
                       'automatic': True, 'scene': scene,
                       'speed': speed if speed is not None else job.review_payload.get('speed', 1.0)}
            job.status = 'queued'
            job.stage = 'queued'
            job.audio = None
            job.error = None
            job.completed = 0
            job.total = 0
            job.speaker = None
            job.delivery = None
            job.scene = scene.public()
            self.pool.submit(self._run, job, payload)
            return job

    def snapshot(self, job_id):
        with self.lock:
            job = self.jobs.get(job_id)
            return job.public() if job else None

    def cancel_job(self, job_id):
        with self.lock:
            job = self.jobs.get(job_id)
            if job and job.status == 'review':
                job.cancel.set()
                job.status = 'cancelled'
            elif job and job.status in {'queued', 'running', 'cancelling'}:
                job.cancel.set()
                job.status = 'cancelling'
            return job.public() if job else None


queue = JobQueue()
