"""bench_folder_open.py — Apertura de carpetas con 100 / 1.000 / 10.000 entradas.

Genera bajo TMPDIR tres carpetas con 100, 1.000 y 10.000 archivos de nombres
variados, instancia un ``Workspace`` (vista principal del gestor) en modo
offscreen y mide cuánto tarda en poblar el modelo tras navegar a cada carpeta
(``workspace.set_root_path``), igual que hace la app al abrir una carpeta.

Metodología:
* Cada repetición usa un ``Workspace`` recién creado (modelo nuevo), anclado a
  un directorio vacío de partida para no contaminar la medida.
* Se cronometra desde justo antes de ``set_root_path(carpeta)`` hasta que
  ``model.rowCount(index_de_la_carpeta)`` alcanza el número esperado de
  entradas (QFileSystemModel puebla en un hilo propio; el bucle drena eventos
  con ``QApplication.processEvents()`` como hacen los tests).
* Se reporta también el tiempo hasta las primeras 25 filas (primeras filas
  visibles para el usuario).

El número de repeticiones se reduce para la carpeta de 10.000 entradas porque
cada apertura tarda varios segundos: 100/1.000 → 5 repeticiones, 10.000 → 3
(ajustable con ``--reps``).

Uso (desde la raíz del repositorio):

    python3 scripts/bench_folder_open.py [--reps N]
"""

from __future__ import annotations

import argparse
import gc
import sys
import time
from pathlib import Path

import _bench_common as bench
from _bench_common import banner, clean_temp_dir, format_summary, isolated_config, make_temp_dir, print_platform_info, summarize, wait_for_rows

bench.bootstrap()

SIZES = (100, 1000, 10000)
REPS = {100: 5, 1000: 5, 10000: 3}


def build_folder(root: Path, count: int) -> Path:
    """Crea una carpeta con ``count`` archivos de nombres variados."""
    target = root / f"carpeta-{count:05d}"
    target.mkdir(parents=True, exist_ok=True)
    for index in range(count):
        suffix = {0: ".txt", 1: ".log", 2: ".dat", 3: ".cfg"}[index % 4]
        (target / f"informe-{index:06d}-item-{index % 13}-lote-{index % 5}{suffix}").touch()
    return target


def measure_open(app, target: Path, expected: int, empty_anchor: Path, timeout: float):
    """Crea un Workspace y mide la navegación a ``target``.

    Devuelve (tiempo_primeras_filas, tiempo_completo) o None si se agota el
    plazo. ``expected`` es el número de entradas a esperar.
    """
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QApplication
    from lfmapp.ui.workspace import Workspace

    ws = Workspace(initial_path=empty_anchor)
    ws.resize(1000, 700)
    ws.show()
    app.processEvents()

    root_index = ws.model.index(str(target))
    first_seen: float | None = None

    def pump():
        app.processEvents()

    start = time.perf_counter()
    ws.set_root_path(target)  # ← la navegación que se cronometra
    deadline = start + timeout
    first_threshold = min(25, expected)
    stable = 0
    while True:
        pump()
        rows = ws.model.rowCount(root_index)
        if first_seen is None and rows >= first_threshold:
            first_seen = time.perf_counter() - start
        if rows >= expected:
            stable += 1
            if stable >= 3:
                full_time = time.perf_counter() - start
                break
        else:
            stable = 0
        if time.perf_counter() > deadline:
            ws.close()
            return (first_seen, None)
    ws.close()
    ws.deleteLater()
    gc.collect()
    return (first_seen, full_time)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reps", type=int, default=None,
                        help="repeticiones por tamaño (por defecto 5/5/3)")
    parser.add_argument("--timeout", type=float, default=150.0,
                        help="plazo máximo por apertura en segundos")
    args = parser.parse_args()

    reps = {size: (args.reps or REPS[size]) for size in SIZES}

    banner("bench_folder_open: apertura de carpetas 100 / 1.000 / 10.000 (offscreen)")
    print_platform_info()
    print("Generando carpetas de prueba bajo TMPDIR (100, 1.000 y 10.000 archivos)…",
          flush=True)
    work_dir = make_temp_dir("lfm-folder-open-")
    try:
        data_root = work_dir / "datos"
        data_root.mkdir()
        folders: dict[int, Path] = {}
        for size in SIZES:
            folders[size] = build_folder(data_root, size)
            print(f"  carpeta con {size} archivos lista: {folders[size]}", flush=True)
        empty_anchor = data_root / "vacia"
        empty_anchor.mkdir()

        from PyQt6.QtWidgets import QApplication
        app = QApplication([])

        print("\nAbrir carpeta = cronometrar set_root_path() hasta que el modelo\n"
              "reporta filas (QFileSystemModel puebla en su propio hilo).\n")
        results: dict[int, list[tuple[float | None, float | None]]] = {}
        for size in SIZES:
            results[size] = []
            for rep in range(reps[size]):
                first_s, full_s = measure_open(app, folders[size], size, empty_anchor, args.timeout)
                results[size].append((first_s, full_s))
                mark = "timeout" if full_s is None else f"{full_s:.4f}s"
                print(f"  {size:6d} entradas · repetición {rep + 1}/{reps[size]}: "
                      f"primeras filas={'n/a' if first_s is None else f'{first_s:.4f}s'} "
                      f"carga completa={mark}", flush=True)

        print("\n" + "-" * 72)
        print("Tabla resumen (segundos; mediana p50 de las repeticiones):")
        print(f"{'entradas':>10} {'reps':>5} {'p50 primeras':>14} {'p50 completo':>14} "
              f"{'min':>8} {'max':>8}")
        for size in SIZES:
            full_times = [full for _, full in results[size] if full is not None]
            first_times = [first for first, _ in results[size] if first is not None]
            if not full_times:
                print(f"{size:>10} {len(results[size]):>5}  (sin datos: todas con timeout)")
                continue
            summary = summarize(full_times)
            first_summary = summarize(first_times) if first_times else None
            print(f"{size:>10} {len(results[size]):>5} "
                  f"{first_summary['p50'] if first_summary else float('nan'):>14.4f} "
                  f"{summary['p50']:>14.4f} {summary['min']:>8.4f} {summary['max']:>8.4f}")
            print("[BENCH] folder_open entradas=" + str(size) +
                  " " + " ".join(
                      f"{k}={int(v)}" if k == "n" else f"{k}={v:.6f}"
                      for k, v in summary.items()
                  ))
    finally:
        clean_temp_dir(work_dir)

    print("\nbench_folder_open terminado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
