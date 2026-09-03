# Línea base de rendimiento — Fase 0.2

> Documento de referencia de la **Fase 0.2** del ROADMAP: medición reproducible
> del rendimiento de linux-file-manager (PyQt6) y presupuestos propuestos.
> Todas las cifras de este documento son **reales**, medidas en la máquina de
> desarrollo indicada abajo con los scripts de `scripts/`, y no copiadas de
> ninguna fuente externa.

- **Fecha de medición**: 2026-09-02 19:23–19:35
- **Máquina**: `avlmxe` — Debian GNU/Linux 13 (trixie), kernel `7.0.10-1-liquorix-amd64`
- **CPU**: Intel Core i3-7020U @ 2,30 GHz (4 hilos)
- **RAM**: 7.833 MiB totales
- **Python**: 3.13.5 · **PyQt6**: 6.9.0 · **Qt**: 6.8.2
- **Plataforma Qt**: `offscreen` (sin servidor X, como en los tests)
- **Versión del paquete**: `linuxfilemanager` 0.1.0 (árbol de trabajo en la fecha indicada)
- **TMPDIR**: `/tmp` (montado como `tmpfs`, RAM respaldada — ver *Limitaciones*)

---

## 1. Objetivo y alcance

La Fase 0.2 pide medir y dejar registrados:

1. Tiempo de **arranque en frío y en caliente** de la aplicación.
2. **Apertura de carpetas** con 100, 1.000 y 10.000 entradas.
3. **Tiempo hasta el primer resultado** de búsqueda.
4. **Consumo de memoria** durante miniaturas y operaciones largas.
5. **Presupuestos de rendimiento** coherentes con lo medido.

No se ha modificado ningún fichero de código de producción: los scripts son
autocontenidos, aíslan la configuración de la aplicación en un directorio
temporal (como hacen los tests) y crean sus propios datos de prueba bajo
`TMPDIR`, borrándolos al terminar.

---

## 2. Metodología general

* Los scripts se ejecutan **desde la raíz del repositorio** (los imports son
  absolutos, `lfmapp.*`). Los procesos hijo de los scripts se lanzan con el
  mismo intérprete y con `QT_QPA_PLATFORM=offscreen` en el entorno.
* La medición es en **offscreen** por reproducibilidad (igual que los tests).
  La resolución de iconos del tema del sistema depende del escritorio; véase
  el hallazgo nº 1 en §6.
* Reloj: `time.perf_counter()`. En cada muestra se informa la mediana **p50**,
  el **p95** (percentil por rango más cercano), la media, el mínimo y el
  máximo. Con N pequeñas (arranque frío, carpeta de 10.000 entradas) el p95
  no es robusto: equivale al máximo de la muestra y así se indica.
* Los datos de prueba se generan bajo `/tmp` (tmpfs): carpetas con 100/1.000/
  10.000 archivos, corpus de búsqueda, PNG para miniaturas.
* La máquina estaba en uso normal durante las mediciones (sesión gráfica y
  otros procesos), por lo que hay dispersión entre repeticiones; se reportan
  medianas.

Duración aproximada por script (esta máquina):

| Script | Duración típica |
|---|---|
| `bench_startup.py` | ~2,5 min (3 muestras frías ≈ 30 s cada una) |
| `bench_folder_open.py` | ~1,5 min |
| `bench_search.py` | < 15 s |
| `bench_memory.py` | ~1 min |

---

## 3. Scripts reproducibles

Todos los scripts imprimen el entorno de medición, una tabla legible y líneas
`[BENCH] clave=valor` (para volcados automáticos).

| Fichero | Qué mide | Uso |
|---|---|---|
| `scripts/bench_startup.py` | Construcción + `show()` de `MainWindow` en frío (proceso nuevo, perfil limpio), con perfil cacheado (2º lanzamiento) y en caliente (mismo proceso) | `python3 scripts/bench_startup.py [--cold-runs N] [--hot-runs N]` |
| `scripts/bench_folder_open.py` | Apertura de carpetas de 100/1.000/10.000 entradas (`set_root_path` hasta que el modelo reporta filas) | `python3 scripts/bench_folder_open.py [--reps N]` |
| `scripts/bench_search.py` | Tiempo hasta el primer resultado y hasta el final de `SearchThread` (plano y recursivo) | `python3 scripts/bench_search.py [--reps N]` |
| `scripts/bench_memory.py` | RSS del proceso en miniaturas (300 PNG) y en la carga+orden+render de 10.000 entradas | `python3 scripts/bench_memory.py` |

Detalles de cada medición:

### 3.1 Arranque (`bench_startup.py`)

* Se cronometra `time.perf_counter()` alrededor de `MainWindow(config)` +
  `show()` + `QApplication.processEvents()`; el dato principal es
  **construcción + show** (ventana lista). El importado de módulos se mide por
  separado en las muestras frías.
* **Frío** = subproceso recién lanzado con perfil limpio: `CONFIG_DIR`/
  `CONFIG_FILE` redirigidos a un directorio temporal **vacío** (sin caché de
  iconos). N=3 por defecto porque cada muestra cuesta ~25–31 s; por ello el
  p95 no es robusto y se reportan mediana/media/min/max.
* **Perfil con caché** = subproceso nuevo que reutiliza el `config.json` que
  dejó una muestra fría (rutas de iconos encontradas, persistidas por la
  propia app) y llama a `initialize_icon_cache(config)`, igual que
  `lfmapp.app.main` en un segundo arranque real.
* **Caliente** = instanciaciones repetidas en el mismo proceso tras una
  primera ventana (calentamiento que carga módulos y caches de iconos);
  N=6 por defecto, se reporta p50/p95.

### 3.2 Apertura de carpetas (`bench_folder_open.py`)

* Cada repetición crea un `Workspace` nuevo anclado a una carpeta vacía y
  cronometra la **navegación real** que hace la aplicación al abrir una
  carpeta: `workspace.set_root_path(carpeta)` hasta que el modelo
  (`QFileSystemModel`, que puebla en su propio hilo) reporta el número
  esperado de filas, drenando eventos con `processEvents()` (patrón idéntico
  al test `test_workspace_handles_directory_with_10000_files`).
* Se informa además el tiempo hasta las **primeras 25 filas** (primeras filas
  visibles). Repeticiones: 100/1.000 → 5, 10.000 → 3.

### 3.3 Búsqueda (`bench_search.py`)

* Usa el servicio real `lfmapp.services.search_service.SearchThread` (el mismo
  que lanza `MainWindow._start_search`) sobre un corpus temporal: **plana** =
  600 archivos con 12 coincidencias (no recursiva, como la barra de búsqueda);
  **recursiva** = el corpus anterior más 1.800 archivos anidados (2.400 en
  total, 42 coincidencias).
* Se cronometra desde `thread.start()` hasta que el slot conectado a la señal
  `found` recibe el **primer resultado** (incluye arranque del hilo y
  entrega de la señal por el bucle de eventos de Qt, que es lo que percibe la
  interfaz) y hasta la señal `finished` (búsqueda completa). N=7.

### 3.4 Memoria (`bench_memory.py`)

* Escenarios en subprocesos propios para atribuir las cifras; datos generados
  una sola vez (300 PNG reales de 128×128 vía `QImage`, 300 `.txt` de control
  y una carpeta de 10.000 archivos).
* RSS **actual** leído de `/proc/self/statm` y **pico** de
  `resource.getrusage().ru_maxrss` (no se depende de `/usr/bin/time`, que no
  está instalado en esta máquina).
* `miniaturas`: `Workspace` sobre los 300 PNG, vista de iconos mostrada y
  generación forzada de las 300 miniaturas (`data(DecorationRole)`), que es lo
  que hace la app al recorrer una carpeta de imágenes con miniaturas activas.
* `iconos` (control): mismo escenario con 300 `.txt` (aisla el coste de las
  miniaturas del coste de la vista de iconos).
* `carga-10k` (operación larga): cargar 10.000 entradas en el modelo, ordenar
  por tamaño y forzar el render de 2.000 filas × 16 columnas, muestreando RSS
  en cada fase y cronometrando cada sub-operación.

---

## 4. Resultados medidos

### 4.1 Arranque (`bench_startup.py`)

**Frío — proceso nuevo, perfil limpio (sin caché de iconos).** N=3:

| Muestra | Ventana lista (s) |
|---|---|
| 1 | 25,64 |
| 2 | 26,04 |
| 3 | 23,21 |
| **p50 / p95 / media** | **25,64 / 26,04 (=max) / 24,96** |

Rango observado en mediciones repetidas del mismo escenario: **23–31 s**
(el primer proceso tras reiniciar la caché de páginas del sistema es el más
lento). Una ventana adicional construida como calentamiento del proceso
principal tardó 20,50 s. El importado de módulos de la UI es marginal
(~0,2 s medidos en proceso nuevo), por lo que la construcción domina el
arranque casi por completo.

**Perfil con caché — 2º lanzamiento real (proceso nuevo con `config.json`
persistido + `initialize_icon_cache`):**

| Ventana lista (s) |
|---|
| **20,62** (construcción 20,07 + show 0,55) |

La mejora frente al frío es pequeña: la caché persiste solo los iconos
**encontrados**; los nombres que no existen en el tema se vuelven a barrer en
cada proceso (ver hallazgo nº 1).

**Caliente — instanciaciones repetidas en el mismo proceso.** N=6:

| Métrica | s |
|---|---|
| p50 | **0,87** |
| p95 | **1,00** |
| media | 0,93 |
| min / max | 0,86 / 1,00 |

> **Lectura**: el arranque frío real hoy ronda los **25 s (p50)** y está
> dominado por la resolución de iconos del sistema; una vez cargados los
> módulos y caches, abrir otra ventana cuesta **~0,9 s**.

### 4.2 Apertura de carpetas (`bench_folder_open.py`)

Tiempo hasta las primeras 25 filas y hasta la carga completa del modelo
(mediana p50 de las repeticiones; rango min–max de la carga completa):

| Entradas | Reps | Primeras 25 filas (p50) | Carga completa (p50) | min / max |
|---|---|---|---|---|
| 100 | 5 | 0,116 s | **0,190 s** | 0,164 / 0,341 s |
| 1.000 | 5 | 0,117 s | **1,265 s** | 1,191 / 1,403 s |
| 10.000 | 3 | 0,157 s | **11,727 s** | 11,616 / 11,940 s |

Las primeras filas aparecen rápido en todos los casos (≤ ~0,16 s); el coste
está en poblar completamente el modelo (`QFileSystemModel` hace stat y
resolución de tipo/icono por entrada). En `bench_memory.py`, con la carpeta
recién creada y la caché de páginas caliente, la carga de 10.000 se midió en
8,15 s, por lo que el valor realista de la operación está en el rango
**8–12 s** según el estado de la caché del sistema de ficheros.

### 4.3 Búsqueda (`bench_search.py`)

N=7. Unidades: milisegundos.

| Escenario | Primer resultado (p50 / p95) | Búsqueda completa (p50 / p95) |
|---|---|---|
| Plana · 600 archivos · 12 coincidencias | **2,97 / 9,33 ms** | 9,99 / 14,03 ms |
| Recursiva · 2.400 archivos · 42 coincidencias | **3,69 / 5,32 ms** | 67,89 / 73,94 ms |

> **Lectura**: el primer resultado llega en unos pocos milisegundos en ambos
> escenarios; el grueso del tiempo de una búsqueda recursiva es el recorrido
> completo del árbol (≈ 68 ms para 2.400 archivos).

### 4.4 Memoria (`bench_memory.py`)

RSS en KiB medidos (MiB entre paréntesis, 1 MiB = 1.024 KiB). Cada escenario
corre en un subproceso; «Δ» es el incremento de RSS actual respecto a la fase
anterior del mismo escenario.

| Fase | RSS actual (KiB / MiB) | Δ |
|---|---|---|
| **base**: solo Qt (proceso sin lfmapp) | 41.784 / 40,8 | — |
| **base**: Qt + imports de lfmapp | ~54.400 / ~53,1 | — |
| **miniaturas**: modelo con 300 PNG cargados | 90.472 / 88,4 | +36.056 KiB |
| **miniaturas**: vista de iconos con 300 miniaturas generadas | 114.536 / **111,9** | +24.064 KiB |
| **iconos (control)**: 300 `.txt` en vista de iconos | 94.972 / 92,7 | +4.696 KiB |
| **carga-10k**: modelo con 10.000 entradas | 100.128 / **97,8** | +45.704 KiB |
| **carga-10k**: tras ordenar por tamaño | 104.144 / 101,7 | +4.016 KiB |
| **carga-10k**: tras render de 2.000 filas × 16 columnas | 104.740 / 102,3 | +596 KiB |

Tiempos de las operaciones (mismo proceso hijo):

| Operación | Tiempo |
|---|---|
| Carga del modelo de 10.000 entradas | 8,15 s |
| Ordenación de 10.000 filas por tamaño | 0,33 s |
| Render forzado 2.000 × 16 columnas | 1,92 s |
| Generación de 300 miniaturas (con caché) | 0,006 s (la caché ya estaba poblada al pintar la vista) |

> **Lectura**: la app con la interfaz cargada ronda **~90–115 MiB** en estos
> escenarios. Las miniaturas de 300 imágenes aportan ~**+20 MiB** respecto a
> la misma vista sin miniaturas (111,9 − 92,7 MiB). Cargar una carpeta de
> 10.000 entradas añade ~**+45 MiB** sobre la base.

---

## 5. Presupuestos de rendimiento propuestos

Criterio: presupuesto = tope que no debe superarse en la plataforma de
referencia (offscreen, esta máquina), con margen sobre lo medido donde lo
medido ya es razonable, y objetivo de optimización explícito donde no lo es
(se indica «requiere optimización»). La verificación se hará con estos mismos
scripts.

| Métrica | Medido (p50) | Presupuesto propuesto | Nota |
|---|---|---|---|
| Arranque frío (perfil limpio, 1ª ventana) | 25,64 s | **≤ 8 s** | Requiere corregir la resolución de iconos (hallazgo nº 1). Meta intermedia ≤ 15 s. |
| 2º lanzamiento con caché de perfil | 20,62 s | **≤ 3 s** | Ídem; la caché debe persistir aciertos y fallos. |
| Arranque caliente (2ª ventana, mismo proceso) | 0,87 s | **≤ 1,0 s** | Ya se cumple en p50; p95 observado 1,00 s. |
| Apertura carpeta 100 entradas | 0,190 s | **≤ 0,5 s** | — |
| Apertura carpeta 1.000 entradas | 1,27 s | **≤ 2,0 s** | — |
| Apertura carpeta 10.000 entradas | 11,7 s | **≤ 8,0 s** | Requiere optimización (rango medido 8–12 s). |
| Búsqueda plana 600: 1er resultado | 2,97 ms | **≤ 30 ms** | Incluye arranque del hilo y entrega de señales. |
| Búsqueda plana 600: completa | 9,99 ms | **≤ 50 ms** | — |
| Búsqueda recursiva 2.400: 1er resultado | 3,69 ms | **≤ 40 ms** | — |
| Búsqueda recursiva 2.400: completa | 67,9 ms | **≤ 150 ms** | — |
| RSS base (UI cargada, sin datos) | ~53 MiB | **≤ 120 MiB** | — |
| RSS con 300 miniaturas en vista de iconos | ~112 MiB | **≤ 250 MiB** | — |
| RSS durante carga/orden de carpeta 10.000 | ~102 MiB | **≤ 250 MiB** | Pico del escenario de prueba. |

---

## 6. Hallazgos para el ROADMAP

1. **El arranque frío está dominado por la resolución de iconos del sistema**
   (`lfmapp/ui/icons.py`). Cuando `QIcon.fromTheme()` falla, la app hace un
   barrido recursivo en Python (`Path.rglob`) de los directorios de temas de
   Qt por cada nombre y extensión; en esta máquina eso recorre millones de
   entradas (~9M `scandir`/`is_dir` en un perfilado) y se repite para ~20
   nombres en cada construcción de `MainWindow`. La caché persistida solo
   guarda aciertos, así que los nombres no encontrados se re-barren en cada
   proceso. Es el mayor coste medible de la fase y el primer objetivo de
   optimización (presupuesto: arranque frío ≤ 8 s). Ideas alineadas con la
   arquitectura actual: persistir también los fallos, limitar el barrido a los
   directorios del tema activo y cachear por proceso sin re-barrer.

   **Estado (implementado 2026-09-03).** Adoptada la estrategia de Thunar/GTK:
   resolver los iconos **solo con el motor del tema activo** (`QIcon.fromTheme`,
   indexado y nativo), sin barridos Python del disco ni sondeo de otros temas.
   El perfil persistido (`cached_icon_paths`) solo restaura rutas de sesiones
   anteriores como último recurso para nombres que el tema activo no ofrece, y
   la caché de iconos resueltos se invalida cuando cambia el tema del sistema.
   El escaneo completo queda como herramienta de mantenimiento opcional
   (`discover_system_icons`) y **nunca se ejecuta durante el arranque**. Medido
   en la misma máquina: construcción de `MainWindow` **11,55 s → ~0,8–1,0 s**
   (≈1,4 s incluyendo `show()` con perfil limpio), con **cero** barridos y una
   sola consulta por nombre/tema (los fallos se cachean). La verificación
   formal con `bench_startup.py` queda como regresión de la Fase 0.2.
2. **Abrir carpetas grandes es el coste interactivo más alto**: 10.000
   entradas tardan 8–12 s en poblarse por completo (las primeras filas salen
   en ~0,16 s). El cuello de botella está en el poblamiento nativo de
   `QFileSystemModel` (stat/resolución por entrada). Aunque es código de Qt, la
   app puede mitigarlo (p. ej. diferir columnas caras o filtrar) en una fase
   posterior.
3. **Búsqueda y memoria están dentro de márgenes sanos**: primer resultado en
   milisegundos y RSS en el orden de los 100 MiB en los escenarios de prueba.

---

## 7. Limitaciones y notas de reproducibilidad

* **offscreen**: la resolución de iconos depende del tema; con un escritorio
  real y un tema completo los tiempos de arranque podrían ser menores. Las
  cifras de este documento son las del entorno reproducible de tests.
* **tmpfs**: `/tmp` es RAM-respaldo; los datos de prueba se crean y leen en
  RAM. En disco físico la creación y la primera lectura de los datos de prueba
  serán más lentas; el coste dominante (stat por entrada) es similar.
* **Máquina compartida**: había otros procesos activos durante las mediciones;
  por eso hay dispersión entre repeticiones y se usan medianas.
* **N pequeñas**: en el arranque frío (N=3) y la carpeta de 10.000 (N=3) el
  p95 coincide con el máximo y no es estadísticamente robusto; se indican
  mediana y rango. El coste por muestra (~25–31 s) hace inviable N=5 por
  defecto; usar `--cold-runs N`.
* **Memoria**: Qt puede no devolver memoria al sistema operativo entre fases;
  los deltas de RSS «actual» por fase son orientativos y las cifras de pico
  (`ru_maxrss`) son el máximo acumulado del proceso. Las mediciones de RSS
  dependen del asignador y de la caché de pixmaps de Qt.
* Para resultados comparables conviene no ejecutar otros benchmarks de forma
  simultánea y medir siempre con los datos recién generados por el propio
  script.

---

## 8. Reproducción

```bash
# Desde la raíz del repositorio (Python ≥ 3.11 con PyQt6):
python3 scripts/bench_startup.py        # ~2,5 min  (--cold-runs N --hot-runs N)
python3 scripts/bench_folder_open.py    # ~1,5 min  (--reps N)
python3 scripts/bench_search.py         # < 15 s    (--reps N)
python3 scripts/bench_memory.py         # ~1 min
```

Cada script imprime el entorno, crea y borra sus datos temporales y termina
con código de salida 0 si todo fue bien. Las líneas `[BENCH]` permiten volcar
los resultados a un fichero para comparar regresiones entre versiones.
