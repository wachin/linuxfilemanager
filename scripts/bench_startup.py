"""bench_startup.py — Línea base del arranque de la ventana principal (Fase 0.2).

Mide la creación de ``MainWindow`` (PyQt6, ``QT_QPA_PLATFORM=offscreen``):

* **Frío**  : proceso nuevo con perfil limpio (sin caché de iconos). Cada
              muestra se ejecuta en un subproceso recién lanzado y con un
              directorio de configuración temporal vacío.
* **Perfil con caché** (segundo lanzamiento real): proceso nuevo que reutiliza
              el directorio de configuración dejado por una muestra fría
              (``config.json`` ya contiene las rutas de iconos encontradas) y
              precarga la caché con ``initialize_icon_cache`` — igual que hace
              ``lfmapp.app.main`` en un arranque normal.
* **Caliente**: instanciaciones repetidas en el *mismo* proceso (módulos,
              caches de iconos y fuentes ya cargados), que es lo que ocurre al
              abrir una segunda ventana o una pestaña nueva pesada.

Metodología de medición: ``time.perf_counter()`` alrededor de
``MainWindow(config)`` + ``show()`` + ``processEvents()``. El dato principal
es el tiempo de construcción; el arranque real completo añade además el
importado de módulos y la creación de ``QApplication`` (se informa por
separado en las muestras frías).

Nota de coste: en perfiles sin caché, la construcción tarda ~30 s porque la
resolución de iconos del tema (``lfmapp.ui.icons``) hace barridos recursivos
del árbol de temas del sistema. Por eso el número de muestras frías es bajo
(N=3 por defecto) y no se reporta un p95 robusto para ese caso: se reportan
mediana/media/min/max. Use ``--cold-runs`` para más muestras.

Uso (desde la raíz del repositorio):

    python3 scripts/bench_startup.py [--cold-runs N] [--hot-runs N]
                                     [--skip-hot] [--skip-cached]
"""

from __future__ import annotations

import argparse
import gc
import sys
import time
from pathlib import Path

import _bench_common as bench
from _bench_common import banner, clean_temp_dir, format_summary, isolated_config, make_temp_dir, print_platform_info, run_child, summarize

# Ancla del inicio real del proceso (sirve para las muestras frías en
# subprocesos: mide también el importado de módulos).
_EXEC_START = time.perf_counter()
SCRIPT = Path(__file__).resolve()

bench.bootstrap()


def _new_qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _isolate_to(config_dir: Path):
    """Redirige CONFIG_DIR/CONFIG_FILE al directorio indicado (persistente)."""
    import lfmapp.core.config as config_module
    config_module.CONFIG_DIR = config_dir
    config_module.CONFIG_FILE = config_dir / "config.json"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def _measure_window(app, config) -> tuple[float, float]:
    """Construye, muestra y procesa eventos de una MainWindow.

    Devuelve (tiempo_construcción, tiempo_show+eventos) en segundos.
    """
    from lfmapp.ui.main_window import MainWindow

    t0 = time.perf_counter()
    window = MainWindow(config=config)
    t1 = time.perf_counter()
    window.show()
    app.processEvents()
    t2 = time.perf_counter()
    window.close()
    window.deleteLater()
    app.processEvents()
    gc.collect()
    return t1 - t0, t2 - t1


def run_cold_sample(config_dir: Path) -> None:
    """Muestra fría: proceso nuevo, perfil limpio (o con caché previa)."""
    from PyQt6.QtWidgets import QApplication
    from lfmapp.core.config import Config
    from lfmapp.ui.icons import initialize_icon_cache

    cached = (config_dir / "config.json").exists()
    _isolate_to(config_dir)
    app = QApplication([])
    config = Config()
    if cached:
        # Como hace lfmapp.app.main en un segundo arranque: precarga las
        # rutas de iconos ya descubiertas.
        initialize_icon_cache(config)
    imports_end = time.perf_counter()

    from lfmapp.ui.main_window import MainWindow

    t0 = time.perf_counter()
    window = MainWindow(config=config)
    t1 = time.perf_counter()
    window.show()
    app.processEvents()
    t2 = time.perf_counter()
    window.close()
    gc.collect()

    kind = "cached" if cached else "cold"
    print(
        f"[BENCH] sample={kind} config_dir={config_dir.name} "
        f"construct_s={t1 - t0:.6f} show_s={t2 - t1:.6f} "
        f"imports_s={imports_end - _EXEC_START:.6f} total_s={t2 - _EXEC_START:.6f}",
        flush=True,
    )
    print(
        f"{kind}: construct={t1 - t0:.3f}s show+eventos={t2 - t1:.3f}s "
        f"imports={imports_end - _EXEC_START:.3f}s total={t2 - _EXEC_START:.3f}s "
        f"(proceso nuevo, config_dir={config_dir.name})"
    )


def run_hot_samples(app, config, hot_runs: int) -> list[float]:
    """Instanciaciones repetidas en el mismo proceso (caliente)."""
    samples: list[float] = []
    for index in range(hot_runs):
        construct_s, show_s = _measure_window(app, config)
        total_s = construct_s + show_s
        samples.append(total_s)
        print(
            f"[BENCH] hot_sample={index} window_s={total_s:.6f} "
            f"construct_s={construct_s:.6f} show_s={show_s:.6f}",
            flush=True,
        )
        print(f"  caliente #{index + 1}: ventana lista en {total_s:.3f}s")
    return samples


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cold-sample", action="store_true", help="modo hijo: una muestra fría")
    parser.add_argument("--cached-sample", action="store_true", help="modo hijo: muestra con perfil ya cacheado")
    parser.add_argument("--config-dir", type=Path, default=None, help="directorio de configuración (modos hijo)")
    parser.add_argument("--cold-runs", type=int, default=3, help="muestras frías (subprocesos)")
    parser.add_argument("--hot-runs", type=int, default=6, help="instanciaciones calientes medibles")
    parser.add_argument("--skip-hot", action="store_true", help="omitir la fase caliente")
    parser.add_argument("--skip-cached", action="store_true", help="omitir la muestra con perfil cacheado")
    args = parser.parse_args()

    if args.cold_sample or args.cached_sample:
        if args.config_dir is None:
            print("--cold-sample/--cached-sample requieren --config-dir", file=sys.stderr)
            return 2
        run_cold_sample(args.config_dir)
        return 0

    # ------------------------------------------------------------------ fase fría
    banner("bench_startup: arranque de MainWindow (offscreen)")
    print_platform_info()
    print("Metodología resumida: ver cabecera del script y docs/performance-baseline.md.\n")

    work_dir = make_temp_dir("lfm-startup-")
    try:
        script = SCRIPT
        cold_samples: list[float] = []
        cold_rows = []
        config_dirs = [work_dir / f"cfg-cold-{i}" for i in range(args.cold_runs)]
        print(f"Fase FRÍA: {args.cold_runs} proceso(s) nuevo(s), perfil limpio "
              f"(config. temporal, sin caché de iconos). Puede tardar ~30 s por muestra.\n")
        for index, config_dir in enumerate(config_dirs):
            print(f"  [{index + 1}/{args.cold_runs}] lanzando subproceso…", flush=True)
            rows = run_child([script, "--cold-sample", "--config-dir", config_dir], timeout=400)
            row = rows[-1] if rows else {}
            construct_s = float(row.get("construct_s", 0.0))
            show_s = float(row.get("show_s", 0.0))
            cold_samples.append(construct_s + show_s)
            cold_rows.append(row)

        cold_summary = summarize(cold_samples)
        print("\nResumen FRÍO (construcción + show, sin imports):")
        print("  " + format_summary(cold_summary))
        for row, value in zip(cold_rows, cold_samples):
            print(f"    muestra config_dir={row.get('config_dir')}: {value:.3f}s")

        # ------------------------------------------------------ perfil con caché
        if not args.skip_cached and config_dirs:
            print("\nFase PERFIL CON CACHÉ (2º lanzamiento real): subproceso nuevo "
                  "reutilizando el config.json de la primera muestra fría "
                  "(rutas de iconos persistidas) + initialize_icon_cache().")
            print("  Puede tardar ~20 s.", flush=True)
            rows = run_child([script, "--cached-sample", "--config-dir", config_dirs[0]], timeout=200)
            row = rows[-1] if rows else {}
            construct_s = float(row.get("construct_s", 0.0))
            show_s = float(row.get("show_s", 0.0))
            print(f"  perfil con caché: ventana lista en {construct_s + show_s:.3f}s "
                  f"(construct={construct_s:.3f}s + show={show_s:.3f}s)")

        # ------------------------------------------------------------- caliente
        if not args.skip_hot:
            print("\nFase CALIENTE (mismo proceso): la 1ª ventana es el calentamiento "
                  "(carga de módulos y caches); a continuación se cronometran "
                  f"{args.hot_runs} instanciaciones repetidas.")
            from PyQt6.QtWidgets import QApplication
            from lfmapp.core.config import Config

            app = QApplication([])
            hot_config_dir = work_dir / "cfg-hot"
            _isolate_to(hot_config_dir)
            hot_config = Config()
            print("  calentamiento (1ª ventana del proceso)…", flush=True)
            warm_s = 0.0
            warm_construct, warm_show = _measure_window(app, hot_config)
            warm_s = warm_construct + warm_show
            cold_samples.append(warm_s)  # también cuenta como muestra fría medida
            cold_rows.append({"config_dir": "proceso-principal", })
            cold_summary_all = summarize(cold_samples)
            print(f"  calentamiento: ventana lista en {warm_s:.3f}s "
                  f"(construct={warm_construct:.3f}s + show={warm_show:.3f}s)")

            hot_samples = run_hot_samples(app, hot_config, args.hot_runs)
            hot_summary = summarize(hot_samples)
            print("\nResumen CALIENTE (instanciaciones repetidas en el mismo proceso):")
            print("  " + format_summary(hot_summary))
            print("\nResumen FRÍO ampliado (hijos + calentamiento del proceso principal):")
            print("  " + format_summary(cold_summary_all))
    finally:
        clean_temp_dir(work_dir)

    print("\nbench_startup terminado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
