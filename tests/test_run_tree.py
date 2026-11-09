"""mm_run.run_tree : au timeout on tue SON arbre de processus, jamais un processus etranger."""
import subprocess
import sys
import time

from mm_run import run_tree

GRANDCHILD = "import time; time.sleep(120)"
CHILD = ("import subprocess, sys, time; "
         f"p = subprocess.Popen([sys.executable, '-c', {GRANDCHILD!r}]); "
         "print(p.pid, flush=True); time.sleep(120)")


def alive(pid):
    if sys.platform.startswith("win"):
        # sortie CSV (colonne PID entre guillemets : pas de faux positif) ; decodage tolerant (page de codes locale)
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"], capture_output=True,
                             text=True, encoding="utf-8", errors="replace").stdout or ""
        return f'"{pid}"' in out
    try:
        import os
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def wait_dead(pid, seconds=10):
    end = time.time() + seconds
    while time.time() < end:
        if not alive(pid):
            return True
        time.sleep(0.2)
    return False


def test_normal_run_returns_output():
    r = run_tree([sys.executable, "-c", "print('ok')"], timeout=20)
    assert r.returncode == 0 and r.stdout.strip() == "ok" and not r.timed_out


def test_failure_code_is_reported():
    r = run_tree([sys.executable, "-c", "import sys; sys.exit(3)"], timeout=20)
    assert r.returncode == 3 and not r.timed_out


def test_timeout_kills_the_whole_tree_but_not_a_bystander():
    bystander = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
    try:
        r = run_tree([sys.executable, "-c", CHILD], timeout=3)
        assert r.timed_out
        grandchild = int(r.stdout.split()[0])
        assert wait_dead(grandchild), "le petit-enfant (l'equivalent d'ffmpeg) doit etre tue avec son parent"
        assert alive(bystander.pid), "un processus etranger ne doit JAMAIS etre tue"
    finally:
        bystander.kill()
        bystander.wait()
