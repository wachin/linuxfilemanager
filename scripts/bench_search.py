"""bench_search.py — Tiempo hasta el primer resultado de búsqueda.

Usa el servicio real ``lfmapp.services.search_service.SearchThread`` (el mismo
que lanza la barra de búsqueda de ``MainWindow._start_search``) sobre un corpus
temporal de varios cientos de archivos:

* Escenario A — plana (no recursiva, igual que la búsqueda de la barra):
  600 archivos en la carpeta raíz, 12 coincidencias con la consulta.
* Escenario B — recursiva: el corpus anterior más 1.800 archivos anidados
  (2.400 en total, 54 coincidencias), con ``recursive=True``.

Qué se mide exactamente: se lanza ``SearchThread`` (QThread) y se cronometra
desde ``start()`` hasta que el *slot* conectado a la señal ``found`` recibe el
primer resultado (el hilo emite la señal y el bucle de eventos la entrega en el
hilo principal, igual que en la app real). Se reporta también el tiempo hasta
la señal ``finished`` (búsqueda completa).

Nota: sobre carpetas de este tamaño la búsqueda es del orden de milisegundos;
el resultado incluye el arranque del hilo y la latencia de entrega de señales
de Qt, que es justo lo que percibe la interfaz.

Uso (desde la raíz del repositorio):

    python3 scripts/bench_search.py [--reps N]
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import _bench_common as bench
from _bench_common import banner, clean_temp_dir, format_summary, make_temp_dir, print_platform_info, summarize

bench.bootstrap()

QUERY = "needle"


def build_corpus(root: Path) -> None:
    """600 archivos planos + 1.800 anidados; 1 de cada N contiene la consulta."""
    for index in range(600):
        if index % 50 == 0:
            name = f"needle_informe-{index:04d}.log"
        else:
            name = f"alpha_{index:04d}.dat"
        (root / name).write_text("x", encoding="utf-8")
    nested = root / "sub" / "nested"
    nested.mkdir(parents=True)
    for index in range(1800):
        if index % 60 == 0:
            name = f"needle_reporte_{index:05d}.md"
        else:
            name = f"beta_{index:05d}.bin"
        (nested / name).write_text("x", encoding="utf-8")


def run_search(app, root: Path, recursive: bool, timeout: float = 30.0):
    """Lanza una búsqueda y devuelve (primer_resultado_s, total_s, coincidencias)."""
    from lfmapp.services.search_service import SearchThread

    first_at: list[float | None] = [None]
    finished: dict[str, int | None] = {"count": None}

    thread = SearchThread(root, QUERY, recursive=recursive)
    start = time.perf_counter()

    def on_found(_path) -> None:
        if first_at[0] is None:
            first_at[0] = time.perf_counter() - start

    def on_finished(count: int) -> None:
        finished["count"] = count

    thread.found.connect(on_found)
    thread.finished.connect(on_finished)
    thread.start()

    deadline = time.perf_counter() + timeout
    while finished["count"] is None and time.perf_counter() < deadline:
        app.processEvents()
        time.sleep(0.0002)
    total_s = time.perf_counter() - start
    thread.wait(5000)
    return first_at[0], total_s, finished["count"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reps", type=int, default=7, help="repeticiones por escenario")
    args = parser.parse_args()

    banner("bench_search: tiempo hasta el primer resultado (offscreen)")
    print_platform_info()
    print(f"Generando corpus bajo TMPDIR (600 archivos planos + 1.800 anidados; "
          f"consulta '{QUERY}')…", flush=True)
    work_dir = make_temp_dir("lfm-search-")
    try:
        root = work_dir / "corpus"
        root.mkdir()
        build_corpus(root)
        print("  corpus listo.\n")

        from PyQt6.QtWidgets import QApplication
        app = QApplication([])

        scenarios = [
            ("plana (no recursiva) · 600 archivos · 12 coincidencias", False, 12),
            ("recursiva · 2.400 archivos · 42 coincidencias", True, 42),
        ]
        for label, recursive, expected_matches in scenarios:
            print(f"Escenario: {label}")
            first_times: list[float] = []
            total_times: list[float] = []
            matches_seen = []
            for rep in range(args.reps):
                first_s, total_s, count = run_search(app, root, recursive)
                first_times.append(first_s if first_s is not None else float("nan"))
                total_times.append(total_s)
                matches_seen.append(count)
                print(f"  rep {rep + 1}/{args.reps}: primer resultado = "
                      f"{first_s * 1000 if first_s is not None else float('nan'):7.2f} ms · "
                      f"búsqueda completa = {total_s * 1000:7.2f} ms · "
                      f"coincidencias = {count}", flush=True)
            first_summary = summarize([t * 1000 for t in first_times if t == t], unit="ms")
            total_summary = summarize([t * 1000 for t in total_times], unit="ms")
            print("  Resumen (ms):")
            print("    hasta el primer resultado : " + format_summary(first_summary, unit="ms"))
            print("    búsqueda completa         : " + format_summary(total_summary, unit="ms"))
            def _b(summ: dict[str, float]) -> str:
                parts = []
                for k, v in summ.items():
                    parts.append(f"{k}={int(v)}" if k == "n" else f"{k}={v:.3f}")
                return " ".join(parts)
            print("[BENCH] search recursive=" + str(int(recursive)) +
                  " first_ms=" + _b(first_summary) +
                  " total_ms=" + _b(total_summary) +
                  f" matches_ok={all(m == expected_matches for m in matches_seen)}")
            print()
    finally:
        clean_temp_dir(work_dir)

    print("bench_search terminado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
