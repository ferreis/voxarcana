"""Restart only this checkout's local studio and its dedicated CPU Ollama."""
import fcntl
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
STATE = Path.home() / '.local/state/voxarcana'
STATE.mkdir(parents=True, exist_ok=True)


def ready(url):
    try:
        with urlopen(url, timeout=2) as response:
            return json.load(response)
    except (OSError, ValueError):
        return None


def listener(port):
    # Linux /proc lets us verify ownership even when a previous run had no PID file.
    inodes = set()
    for table in ('tcp', 'tcp6'):
        for line in Path('/proc/net', table).read_text().splitlines()[1:]:
            fields = line.split()
            if int(fields[1].split(':')[1], 16) == port and fields[3] == '0A':
                inodes.add(fields[9])
    pids = set()
    for process in Path('/proc').iterdir():
        if not process.name.isdigit():
            continue
        try:
            for fd in (process / 'fd').iterdir():
                target = os.readlink(fd)
                if target.startswith('socket:[') and target[8:-1] in inodes:
                    pids.add(int(process.name))
        except (OSError, PermissionError):
            continue
    return pids


def owned(pid, service):
    try:
        process = Path('/proc') / str(pid)
        if process.stat().st_uid != os.getuid():
            return False
        command = (process / 'cmdline').read_bytes().split(b'\0')
        cwd = (process / 'cwd').resolve()
        if service == 'backend':
            return cwd == ROOT / 'backend' and b'uvicorn' in command and b'app.main:app' in command and b'8765' in command
        env = (process / 'environ').read_bytes().split(b'\0')
        return any(Path(arg.decode()).name == 'ollama' for arg in command if arg) and b'serve' in command and b'OLLAMA_HOST=127.0.0.1:11435' in env and b'CUDA_VISIBLE_DEVICES=-1' in env
    except (OSError, ValueError):
        return False


def stop(service, port):
    pids = listener(port)
    pidfile = STATE / f'{service}.pid'
    try:
        pid = int(pidfile.read_text())
        if owned(pid, service):
            pids.add(pid)
    except (OSError, ValueError):
        pass
    for pid in pids:
        if not owned(pid, service):
            raise RuntimeError(f'Porta {port} ocupada por outro serviço (PID {pid}). Nenhum processo desconhecido foi encerrado.')
    for pid in pids:
        print(f'Reiniciando {service} (PID {pid})…', flush=True)
        os.kill(pid, signal.SIGTERM)
    deadline = time.monotonic() + 12
    while any(owned(pid, service) for pid in pids) and time.monotonic() < deadline:
        time.sleep(.2)
    for pid in pids:
        if owned(pid, service):
            os.kill(pid, signal.SIGKILL)
    deadline = time.monotonic() + 5
    while listener(port) and time.monotonic() < deadline:
        time.sleep(.1)
    if listener(port):
        raise RuntimeError(f'A porta {port} ainda está ocupada.')
    pidfile.unlink(missing_ok=True)


def start(service, command, env, url):
    logfile = STATE / ('backend-br.log' if service == 'backend' else 'reader.log')
    with logfile.open('ab') as log:
        process = subprocess.Popen(command, cwd=ROOT / 'backend', env=env,
                                   stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                   start_new_session=True)
    (STATE / f'{service}.pid').write_text(str(process.pid))
    for _ in range(150):
        if process.poll() is not None:
            raise RuntimeError(f'{service} encerrou durante a inicialização. Consulte {logfile}')
        if ready(url):
            return
        time.sleep(.2)
    raise RuntimeError(f'{service} ainda não respondeu. Consulte {logfile}')


def main():
    with (STATE / 'restart.lock').open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Outro reinício do estúdio já está em andamento.')
        # Validate both ports before stopping either service.
        for service, port in [('backend', 8765), ('reader', 11435)]:
            for pid in listener(port):
                if not owned(pid, service):
                    raise RuntimeError(f'A porta {port} está em uso por outro serviço (PID {pid}).')
        stop('backend', 8765)
        stop('reader', 11435)
        env = os.environ.copy()
        reader_env = {**env, 'OLLAMA_HOST': '127.0.0.1:11435',
                      'CUDA_VISIBLE_DEVICES': '-1', 'OLLAMA_NO_CLOUD': '1'}
        start('reader', ['ollama', 'serve'], reader_env, 'http://127.0.0.1:11435/api/tags')
        start('backend', [str(ROOT / 'backend/.venv-br/bin/python'), '-m', 'uvicorn',
                         'app.main:app', '--host', '127.0.0.1', '--port', '8765'],
              {**env, 'VOXARCANA_ENGINE': 'chatterbox-br',
               'PYTORCH_CUDA_ALLOC_CONF': 'expandable_segments:True'}, 'http://127.0.0.1:8765/health')
        print('\nEstúdio pronto: http://127.0.0.1:8765\nBackend e interface ativos. Analisador Ollama na CPU (porta 11435).')
        print(f'Logs: {STATE}\nVozes e classificações foram preservadas.')


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, OSError) as error:
        print(f'Não foi possível reiniciar: {error}', file=sys.stderr)
        sys.exit(1)
