"""Execution d'un sous-processus avec timeout qui tue SEULEMENT son propre arbre de processus.

L'ancien ``taskkill /IM ffmpeg.exe /F`` detruisait tous les ffmpeg de la machine, y compris ceux d'autres
travaux. Ici on garde le PID du processus lance et on supprime ce PID et ses enfants, rien d'autre.
"""
import os
import signal
import subprocess
import sys
from types import SimpleNamespace


def kill_tree(proc):
    """Tue ``proc`` et tous ses descendants (et eux seulement)."""
    if proc.poll() is not None:
        return
    if sys.platform.startswith("win"):
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            proc.kill()


def run_tree(cmd, timeout, **kw):
    """Comme ``subprocess.run(capture_output=True, text=True)`` mais, au timeout, tue l'arbre du processus.

    Retourne un objet avec ``returncode``, ``stdout``, ``stderr`` et ``timed_out``.
    """
    kw.setdefault("encoding", "utf-8")
    kw.setdefault("errors", "replace")
    popen_kw = {}
    if sys.platform.startswith("win"):
        popen_kw["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        popen_kw["start_new_session"] = True
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, **popen_kw, **kw)
    try:
        out, err = proc.communicate(timeout=timeout)
        return SimpleNamespace(returncode=proc.returncode, stdout=out or "", stderr=err or "", timed_out=False)
    except subprocess.TimeoutExpired:
        kill_tree(proc)
        try:
            out, err = proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            out, err = "", ""
        return SimpleNamespace(returncode=-1, stdout=out or "", stderr=err or "", timed_out=True)
