"""bench_memory.py — Consumo de memoria (RSS) en miniaturas y operaciones largas.

Mide el RSS del proceso en varias fases, usando ``/proc/self/statm`` (RSS
actual) y ``resource.getrusage().ru_maxrss`` (pico). No depende de
``/usr/bin/time`` (que puede no estar instalado).

Escenarios (cada uno en un subproceso propio para que las cifras sean
atribuibles; los datos de prueba se crean una sola vez bajo TMPDIR):

* ``base``      — QApplication + imports (memoria base del proceso).
* ``miniaturas``— Workspace sobre 300 PNG reales (128×128 generados con
                  QImage); se pasa a vista de iconos, se muestra la ventana y
                  se fuerza la generación de las 300 miniaturas
                  (``data(DecorationRole)``), que es lo que hace la app al
                  navegar por una carpeta de imágenes con miniaturas activas.
* ``iconos``    — control: Workspace sobre 300 archivos .txt en vista de
                  iconos (mismo coste de vista, sin miniaturas), para aislar
                  el coste atribuible a las miniaturas.
* ``carga-10k`` — operación larga: cargar una carpeta de 10.000 archivos en el
                  modelo, ordenarla por tamaño y forzar el render de 2.000
                  filas × 16 columnas; se mide RSS durante el proceso y el
                  tiempo de cada sub-operación.

Uso (desde la raíz del repositorio):

    python3 scripts/bench_memory.py
"""

from __future__ import annotations

import argparse
import gc
import sys
import time
from pathlib import Path

import _bench_common as bench
from _bench_common import (banner, clean_temp_dir, isolated_config, make_temp_dir,
                           memory_line, peak_rss_kb, print_platform_info, run_child,
                           wait_for_rows)

bench.bootstrap()

SCRIPT = Path(__file__).resolve()
NUM_IMAGES = 300
NUM_BIG = 10000


# ---------------------------------------------------------------- generación
def create_pngs(directory: Path, count: int) -> None:
    """Crea ``count`` PNG pequeños (128×128) con contenido variado (QImage)."""
    from PyQt6.QtGui import QColor, QImage

    directory.mkdir(parents=True, exist_ok=True)
    for index in range(count):
        image = QImage(128, 128, QImage.Format.Format_RGB32)
        for x in range(0, 128, 4):
            for y in range(0, 128, 4):
                color = QColor((index * 7 + x * 3) % 256,
                               (index * 13 + y * 5) % 256,
                               (index * 29 + x + y) % 256)
                image.setPixel(x, y, color.rgb())
        if not image.save(str(directory / f"foto-{index:04d}.png")):
            raise RuntimeError(f"No se pudo guardar el PNG {index}")


def create_text_files(directory: Path, count: int) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for index in range(count):
        (directory / f"doc-{index:04d}.txt").write_text("contenido de prueba", encoding="utf-8")


def create_big_folder(directory: Path, count: int) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for index in range(count):
        (directory / f"registro-{index:06d}.log").write_text("x", encoding="utf-8")


# ------------------------------------------------------------ modos hijo
def child_base() -> int:
    from PyQt6.QtWidgets import QApplication
    app = QApplication([])  # noqa: F841
    gc.collect()
    memory_line("app_base")
    return 0


def _workspace_icon_scenario(directory: Path, label: str, count: int, timeout: float) -> int:
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QApplication
    from lfmapp.ui.workspace import ViewMode, Workspace

    app = QApplication([])
    gc.collect()
    memory_line("app_base")

    with isolated_config():
        ws = Workspace(initial_path=directory)
        root_index = ws.model.index(str(directory))
        elapsed = wait_for_rows(ws.model, root_index, count, app.processEvents, timeout)
        if elapsed is None:
            print(f"ERROR: el modelo no alcanzó {count} filas a tiempo", file=sys.stderr)
            return 1
        print(f"[BENCH] op=model_load_{label} s={elapsed:.4f}", flush=True)
        memory_line(f"modelo_{label}")

        ws.set_view_mode(ViewMode.ICON)
        ws.resize(1100, 850)
        ws.show()
        app.processEvents()
        # Fuerza la generación de miniatura/icono para TODAS las filas (equivale
        # a recorrer la carpeta con miniaturas activas; el modelo cachea).
        held: list[object] = []
        decode_start = time.perf_counter()
        for row in range(count):
            index = ws.model.index(row, 0, root_index)
            held.append(ws.model.data(index, Qt.ItemDataRole.DecorationRole))
        app.processEvents()
        decode_s = time.perf_counter() - decode_start
        cache_size = len(ws.model._thumbnail_cache)
        print(f"[BENCH] op=decode_{label} s={decode_s:.4f} cache_items={cache_size}", flush=True)
        memory_line(f"vista_{label}")
        ws.close()
    return 0


def child_thumbs(directory: Path) -> int:
    return _workspace_icon_scenario(directory, "miniaturas_300png", NUM_IMAGES, 60.0)


def child_icons(directory: Path) -> int:
    return _workspace_icon_scenario(directory, "iconos_300txt", NUM_IMAGES, 60.0)


def child_longop(directory: Path) -> int:
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QApplication
    from lfmapp.ui.workspace import Workspace

    app = QApplication([])
    gc.collect()
    memory_line("app_base")

    with isolated_config():
        ws = Workspace(initial_path=directory)
        root_index = ws.model.index(str(directory))
        elapsed = wait_for_rows(ws.model, root_index, NUM_BIG, app.processEvents, 180.0)
        if elapsed is None:
            print("ERROR: no se cargaron las 10.000 filas a tiempo", file=sys.stderr)
            return 1
        print(f"[BENCH] op=model_load_10k s={elapsed:.4f}", flush=True)
        memory_line("modelo_10k")

        # Operación larga 1: ordenar las 10.000 filas por tamaño (descendente).
        ws.resize(1000, 700)
        ws.show()
        app.processEvents()
        sort_start = time.perf_counter()
        ws.sort_by("size", Qt.SortOrder.DescendingOrder)
        app.processEvents()
        sort_s = time.perf_counter() - sort_start
        print(f"[BENCH] op=sort_10k_por_tamano s={sort_s:.4f}", flush=True)
        memory_line("ordenado_10k")

        # Operación larga 2: forzar el render (data de todas las columnas) de
        # las primeras 2.000 filas, como al pintar la vista de detalles.
        render_rows = min(2000, NUM_BIG)
        render_start = time.perf_counter()
        for row in range(render_rows):
            for column in range(ws.model.columnCount()):
                ws.model.data(ws.model.index(row, column, root_index),
                              Qt.ItemDataRole.DisplayRole)
        render_s = time.perf_counter() - render_start
        print(f"[BENCH] op=render_{render_rows}x16 s={render_s:.4f}", flush=True)
        memory_line("render_2000_filas")
        ws.close()
    return 0


CHILDREN = {
    "base": child_base,
    "miniaturas": child_thumbs,
    "iconos": child_icons,
    "carga-10k": child_longop,
}
# ------------------------------------------------------------------- principal
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--child", choices=sorted(CHILDREN), default=None,
                        help="modo hijo (lo usa el propio script; no invocar a mano)")
    parser.add_argument("--dir", type=Path, default=None, help="directorio de datos (modo hijo)")
    args = parser.parse_args()

    if args.child is not None:
        if args.child == "base":
            return child_base()
        if args.dir is None:
            print("--child requiere --dir", file=sys.stderr)
            return 2
        return CHILDREN[args.child](args.dir)

    banner("bench_memory: RSS en miniaturas y operaciones largas (offscreen)")
    print_platform_info()
    print("Preparando datos de prueba bajo TMPDIR…", flush=True)

    from PyQt6.QtWidgets import QApplication
    app = QApplication([])  # noqa: F841  (necesaria para generar PNG con QImage)

    work_dir = make_temp_dir("lfm-memory-")
    try:
        img_dir = work_dir / "imagenes-300"
        txt_dir = work_dir / "textos-300"
        big_dir = work_dir / "grande-10k"
        print(f"  generando {NUM_IMAGES} PNG de 128×128…", flush=True)
        create_pngs(img_dir, NUM_IMAGES)
        print(f"  generando {NUM_IMAGES} archivos .txt…", flush=True)
        create_text_files(txt_dir, NUM_IMAGES)
        print(f"  generando {NUM_BIG} archivos de registro…", flush=True)
        create_big_folder(big_dir, NUM_BIG)
        print("  datos listos.\n")

        scenarios = [
            ("base", "Solo QApplication + imports", None),
            ("miniaturas", "300 miniaturas PNG en vista de iconos", img_dir),
            ("iconos", "300 .txt en vista de iconos (control sin miniaturas)", txt_dir),
            ("carga-10k", "Carga + orden + render de carpeta con 10.000 entradas", big_dir),
        ]
        collected: dict[str, list[dict[str, str]]] = {}
        ops: dict[str, list[dict[str, str]]] = {}
        for key, label, data_dir in scenarios:
            print(f"Escenario «{key}» — {label}")
            if data_dir is None:
                rows = run_child([SCRIPT, "--child", key], timeout=120)
            else:
                rows = run_child([SCRIPT, "--child", key, "--dir", data_dir], timeout=300)
            mem_rows = [row for row in rows if "mem_phase" in row]
            op_rows = [row for row in rows if "op" in row]
            collected[key] = mem_rows
            ops[key] = op_rows
            for row in mem_rows:
                print(f"  fase {row['mem_phase']:22s} RSS={int(row['rss_kb']):>8,} KiB  "
                      f"pico={int(row['peak_kb']):>8,} KiB")
            for row in op_rows:
                print(f"  operación {row['op']:22s} {float(row['s']):8.3f} s"
                      + (f"  (caché miniaturas: {row['cache_items']} ítems)" if "cache_items" in row else ""))
            print(flush=True)

        print("-" * 72)
        print("Resumen (KiB). Δ = incremento de RSS actual respecto a la fase "
              "anterior del mismo escenario;")
        print("«pico» es ru_maxrss del proceso hijo (RSS máximo alcanzado).")
        for key, label in (
            ("base", "base"),
            ("miniaturas", "miniaturas"),
            ("iconos", "iconos (control)"),
            ("carga-10k", "carga-10k"),
        ):
            rows = collected.get(key, [])
            if not rows:
                continue
            print(f"\n  [{key}] {label}")
            previous: int | None = None
            for row in rows:
                rss = int(row["rss_kb"])
                delta = "" if previous is None else f"  Δ {rss - previous:+,} KiB"
                print(f"    {row['mem_phase']:22s} RSS {rss:>8,} KiB  pico {int(row['peak_kb']):>8,} KiB{delta}")
                previous = rss
    finally:
        clean_temp_dir(work_dir)

    print("\nbench_memory terminado. RSS pico total del proceso padre: "
          f"{peak_rss_kb():,} KiB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
