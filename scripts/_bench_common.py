"""Utilidades comunes de los benchmarks de rendimiento (Fase 0.2 del ROADMAP).

Los scripts de esta carpeta son autocontenidos y reproducibles:

    python3 scripts/bench_startup.py
    python3 scripts/bench_folder_open.py
    python3 scripts/bench_search.py
    python3 scripts/bench_memory.py

Deben ejecutarse desde la raíz del repositorio (así se resuelve el paquete
``lfmapp``). Cada script aísla la configuración de la aplicación en un
directorio temporal y crea sus propios datos de prueba bajo ``TMPDIR``; no se
modifica ningún fichero del usuario ni código de producción.

Convención de salida: las líneas con prefijo ``[BENCH] clave=valor`` son
máquina-legibles (las usan los procesos hijo/padre); el resto es para humanos.
"""

from __future__ import annotations

import gc
import os
import platform
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def bootstrap() -> None:
    """Hace importable el paquete ``lfmapp`` y fuerza Qt 'offscreen'.

    ``QT_QPA_PLATFORM`` debe estar definido antes de importar PyQt6, por eso
    esta función se llama al principio de cada script (los tests hacen lo
    mismo con ``os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")``).
    """
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def banner(title: str) -> None:
    print("=" * 78)
    print(title)
    print("=" * 78, flush=True)


def platform_info() -> dict[str, str]:
    """Datos de la máquina donde se ejecuta la medición (para el informe)."""
    info: dict[str, str] = {}
    info["fecha"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    info["hostname"] = platform.node()
    info["sistema"] = platform.system()
    info["kernel"] = platform.release()
    info["distro"] = " ".join(part for part in platform.freedesktop_os_release().values() if part) \
        if hasattr(platform, "freedesktop_os_release") else platform.version()
    cpu_model = "desconocido"
    try:
        with open("/proc/cpuinfo", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if line.lower().startswith("model name"):
                    cpu_model = line.split(":", 1)[1].strip()
                    break
    except OSError:
        pass
    info["cpu"] = cpu_model
    info["cpu_nucleos"] = str(os.cpu_count() or 0)
    mem_total = 0
    try:
        with open("/proc/meminfo", encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("MemTotal"):
                    mem_total = int(line.split()[1]) // 1024  # KiB -> MiB
                    break
    except OSError:
        pass
    info["mem_total_mib"] = str(mem_total)
    info["python"] = platform.python_version()
    try:
        from PyQt6.QtCore import PYQT_VERSION_STR, QT_VERSION_STR  # type: ignore
        info["pyqt"] = PYQT_VERSION_STR
        info["qt"] = QT_VERSION_STR
    except Exception:
        info["pyqt"] = "n/d"
        info["qt"] = "n/d"
    try:
        from PyQt6.QtWidgets import QApplication  # type: ignore
        info["qt_platform"] = QApplication.platformName() if QApplication.instance() else os.environ.get("QT_QPA_PLATFORM", "n/d")
    except Exception:
        info["qt_platform"] = os.environ.get("QT_QPA_PLATFORM", "n/d")
    info["tmpdir"] = tempfile.gettempdir()
    return info


def print_platform_info() -> None:
    info = platform_info()
    print("Entorno de medición:")
    for key, label in (
        ("fecha", "Fecha"),
        ("hostname", "Host"),
        ("sistema", "Sistema"),
        ("kernel", "Kernel"),
        ("cpu", "CPU"),
        ("cpu_nucleos", "Núcleos"),
        ("mem_total_mib", "Mem total (MiB)"),
        ("python", "Python"),
        ("pyqt", "PyQt6"),
        ("qt", "Qt"),
        ("qt_platform", "Plataforma Qt"),
        ("tmpdir", "TMPDIR"),
    ):
        print(f"  {label:14s}: {info[key]}")
    print(flush=True)


def percentile(sorted_samples: list[float], pct: float) -> float:
    """Percentil por rango más cercano sobre una lista ya ordenada."""
    if not sorted_samples:
        return float("nan")
    idx = min(len(sorted_samples) - 1, max(0, round((pct / 100.0) * (len(sorted_samples) - 1))))
    return sorted_samples[idx]


def summarize(samples: list[float], unit: str = "s") -> dict[str, float]:
    """Estadísticos básicos de una muestra (p50, p95, media, min, max)."""
    ordered = sorted(s for s in samples if s == s)  # descarta NaN
    if not ordered:
        return {"n": 0, "p50": float("nan"), "p95": float("nan"),
                "media": float("nan"), "min": float("nan"), "max": float("nan")}
    return {
        "n": len(ordered),
        "p50": percentile(ordered, 50),
        "p95": percentile(ordered, 95),
        "media": statistics.fmean(ordered),
        "min": ordered[0],
        "max": ordered[-1],
    }


def format_summary(summary: dict[str, float], unit: str = "s") -> str:
    return (
        f"n={summary['n']} p50={summary['p50']:.4f}{unit} "
        f"p95={summary['p95']:.4f}{unit} media={summary['media']:.4f}{unit} "
        f"min={summary['min']:.4f}{unit} max={summary['max']:.4f}{unit}"
    )


@contextmanager
def isolated_config():
    """Aísla la configuración de lfmapp en un directorio temporal.

    Los benchmarks no deben leer ni escribir la configuración real del
    usuario (~/.local/share/linux-file-manager/config.json); redirigimos
    CONFIG_DIR/CONFIG_FILE a un directorio temporal, igual que hacen los
    tests.
    """
    import lfmapp.core.config as config_module

    old_dir = config_module.CONFIG_DIR
    old_file = config_module.CONFIG_FILE
    tmp_dir = Path(tempfile.mkdtemp(prefix="lfm-bench-config-"))
    config_module.CONFIG_DIR = tmp_dir
    config_module.CONFIG_FILE = tmp_dir / "config.json"
    try:
        yield tmp_dir
    finally:
        config_module.CONFIG_DIR = old_dir
        config_module.CONFIG_FILE = old_file
        gc.collect()
        shutil.rmtree(tmp_dir, ignore_errors=True)


def make_temp_dir(prefix: str) -> Path:
    """Directorio temporal (respeta TMPDIR) para datos de prueba."""
    return Path(tempfile.mkdtemp(prefix=prefix))


def clean_temp_dir(path: Path) -> None:
    shutil.rmtree(path, ignore_errors=True)


def run_child(args: list[str], timeout: float = 300) -> list[dict[str, str]]:
    """Ejecuta el mismo script (o uno indicado) en un subproceso nuevo.

    Devuelve los pares clave/valor de las líneas ``[BENCH]`` que el hijo
    imprime. El primer elemento de ``args`` es la ruta del script.
    """
    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    cmd = [sys.executable, str(args[0]), *[str(a) for a in args[1:]]]
    proc = subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr)
        raise RuntimeError(f"El subproceso falló (exit={proc.returncode}): {' '.join(cmd)}")
    rows: list[dict[str, str]] = []
    for line in proc.stdout.splitlines():
        if line.startswith("[BENCH] "):
            row: dict[str, str] = {}
            for token in line[len("[BENCH] "):].split():
                if "=" in token:
                    key, _, value = token.partition("=")
                    row[key] = value
            if row:
                rows.append(row)
    return rows


def wait_for_rows(model, root_index, expected: int, pump, timeout: float,
                  quiet: bool = True) -> float | None:
    """Procesa eventos hasta que el modelo reporte ``expected`` filas.

    QFileSystemModel puebla en un hilo propio; hay que dejar correr el bucle
    de eventos (igual que en los tests) hasta que ``rowCount`` alcance el
    número esperado. Devuelve los segundos transcurridos o None si se agota
    el plazo.
    """
    start = time.perf_counter()
    stable_checks = 0
    while time.perf_counter() - start < timeout:
        pump()
        if model.rowCount(root_index) >= expected:
            stable_checks += 1
            if stable_checks >= 3:  # evita medir una población a medio hacer
                return time.perf_counter() - start
        else:
            stable_checks = 0
    return None


def current_rss_kb() -> int:
    """RSS actual del proceso en KiB leyendo /proc/self/statm (Linux)."""
    try:
        with open("/proc/self/statm", encoding="utf-8") as fh:
            resident_pages = int(fh.read().split()[1])
        page = os.sysconf("SC_PAGESIZE")
        return resident_pages * page // 1024
    except (OSError, IndexError, ValueError):
        return -1


def peak_rss_kb() -> int:
    """RSS pico (ru_maxrss) del proceso en KiB."""
    import resource
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss


def memory_line(phase: str) -> str:
    """Línea [BENCH] con RSS actual y pico para una fase."""
    cur = current_rss_kb()
    peak = peak_rss_kb()
    print(f"[BENCH] mem_phase={phase} rss_kb={cur} peak_kb={peak}", flush=True)
    return f"{phase}: rss={cur} KiB, pico={peak} KiB"
