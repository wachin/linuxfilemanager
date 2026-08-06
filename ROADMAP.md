# ROADMAP.md — Linux File Manager

Última actualización: 2026-08-05

Resume el estado real del proyecto, lo ya conseguido, lo pendiente y dónde mirar primero.

## Identidad del proyecto

- Nombre del proyecto: `linux-file-manager`
- Paquete Python principal: `lfmapp`
- Objetivo: gestor de archivos ligero para Linux, escrito en Python + PyQt6
- Enfoque: rendimiento, estabilidad, productividad del usuario, empaquetado Debian y experiencia de uso práctica

Nota importante:
- Se renombró internamente a `lfmapp` para evitar conflicto con el paquete `lfm` ya existente en Debian.

## Principios de diseño

El gestor debe ser rápido de usar, con acciones visibles y accesibles, sin sacrificar claridad:

- Priorizar atajos y acciones con un solo gesto para operaciones frecuentes.
- Mantener el contexto del usuario: navegación accesible, dirección editable y resultados claros.
- Evitar interrupciones innecesarias: preferir feedback en línea sobre modales excesivos.
- Usar iconos y texto consistentes para reducir la carga cognitiva.
- Ofrecer un flujo de trabajo que combine exploración y acción sin pasos redundantes.

## Diseño de interacción

Casos de uso clave a priorizar:

- Navegar entre carpetas con teclado y ratón sin perder la selección o el contexto.
- Copiar/mover archivos con un diálogo de conflicto claro, acciones predecibles y aplicar a todos.
- Renombrar rápido desde la vista `Details` o con un comando directo.
- Buscar y filtrar dentro de una carpeta con resultados instantáneos y filtros guardados.
- Previsualizar archivos sin abrir aplicaciones externas, con opción de cerrar la vista rápidamente.
- Mantener un panel lateral estable con accesos directos, estado de operación y resultados recientes.

## Inspiración clave

- Diferenciar entre filtrado y búsqueda estructurada: el filtrado actúa sobre la vista actual y oculta elementos no relevantes, mientras que la búsqueda construye listas de resultados a partir de una ubicación y criterios más amplios.
- Ofrecer un filtro rápido accesible por teclado que se active inmediatamente, muestre el número de elementos ocultos y permita limpiar con `Esc`.
- Implementar un modo "Mostrar todo" que desactive temporalmente los filtros visuales del panel actual sin perder la configuración subyacente.
- El campo de filtro debe poder ser persistente en la barra o emergente, pero siempre controlar el mismo estado de filtro rápido y respetar filtros globales y formatos de carpeta.
- Las opciones de filtrado avanzado deben incluir coincidencia parcial, ignorar diacríticos, modo "any word", expresiones regulares y cláusulas complejas basadas en atributos.
- La selección debe ser una fuente de verdad: contar archivos/carpetas seleccionados, mostrar totales de tamaño, y ofrecer selección automática por patrón, extensión, duplicados y otros criterios útiles.
- El ordenamiento y la agrupación deben ser controlables desde los encabezados de columna, con soporte para campos no visibles y modificadores de teclado para invertir o añadir niveles.
- El flujo de copia/movido debe tratar explícitamente origen y destino: en paneles duales, un panel es fuente y el otro destino; en modo único, el usuario debe poder activar el origen/destino mediante foco, atajo o alternancia sin perder selección.
- La cola de operaciones debe ejecutar trabajos secuencialmente cuando convenga, con reglas de priorización basadas en dispositivo, destino y tipo de fuente, y permitir gestión manual de trabajos en espera.
- Los favoritos y accesos rápidos deben estar disponibles en barras, menús y listas, con soporte para arrastrar y soltar, alias de ruta y rutas recientes.
- El historial de navegación debe existir tanto global como por panel, y ser accesible desde el control de ruta, los botones Atrás/Adelante y menús desplegables.
- La barra de estado debe mostrar información relevante como selección, tamaño total, ítems ocultos, formato actual y espacio libre en el dispositivo.
- Los resultados de búsqueda y duplicados deben poder mostrarse en espacios virtuales o colecciones que se comporten como carpetas sin perder la consulta original.
- Los favoritos, accesos rápidos y aliases deben ser accesibles desde la barra lateral, la barra de herramientas y la paleta, con soporte para arrastrar y soltar, renombrar y abrir en contexto.
- El historial de navegación debe ser accesible tanto globalmente como por panel, con listas recientes en la barra de ruta y atajos de atrás/adelante claramente visibles.
- El panel utilitario debe poder contener herramientas como búsqueda avanzada, sincronización y búsqueda de duplicados sin interrumpir el flujo principal.

## Estado actual resumido

El proyecto ya tiene una base funcional amplia. No está en fase inicial. Ya existen:

- Ventana principal con barra de menú, barra de herramientas, barra de estado y paneles.
- Sidebar por pestañas con `Quick Access`, `This Computer`, `Network`, `Bookmarks` y `Recents`.
- Navegación por historial y barra de dirección editable.
- Experiencia de teclado y paleta de comandos empezada, con foco en acceso rápido a acciones clave.
- Operaciones de archivos: copiar, cortar, pegar, renombrar, eliminar, enviar a papelera.
- Vistas `Icons`, `List`, `Details` y `Compact`.
- Menú contextual moderno configurable.
- Soporte XDG para carpetas de usuario localizadas.
- Vista previa lateral funcional.
- Miniaturas de imágenes en el área principal del gestor.
- Persistencia de configuración y recreación automática de archivos de datos faltantes.
- Base orientada a empaquetado Debian.

## Logros confirmados

- [x] Renombrado técnico del proyecto a `lfmapp` para evitar conflicto con `lfm` de Debian.
- [x] Helper de iconos en tiempo de ejecución para preferir iconos del sistema con fallback seguro.
- [x] Uso de iconos del sistema desde `/usr/share/icons/` en vez de depender de Tabler.
- [x] Corrección del icono de la aplicación para que aparezca también en la barra de tareas.
- [x] Sidebar rediseñado en pestañas compactas con iconos para las cinco secciones principales.
- [x] Soporte correcto de XDG User Directories para `Desktop`, `Documents`, `Downloads`, `Music`, `Pictures` y `Videos`.
- [x] `Quick Access` usa las rutas reales del sistema y ya no duplica esas carpetas dentro de `Bookmarks`.
- [x] `This Computer` y `Bookmarks` quedaron mejor separados conceptualmente.
- [x] Corrección de “Open in Terminal” para respetar la terminal configurada en preferencias.
- [x] Eliminación del comportamiento que abría terminales maximizadas o en fullscreen.
- [x] Prioridad por defecto de terminales cambiada para preferir `qterminal`.
- [x] Documentación añadida sobre la ubicación de la configuración y cómo resetear el programa borrando `~/.local/share/linux-file-manager/`.
- [x] Recreación automática al iniciar de archivos y carpetas de datos faltantes, como `config.json`, `bookmarks.json`, `tags.db`, `extensions/` y `vault/`.
- [x] Columnas de `Details` ahora movibles y redimensionables.
- [x] Menú `List Columns` accesible con clic derecho sobre el encabezado.
- [x] Nuevas columnas implementadas en `Details`: `Created - Time`, `Date Accessed`, `Date Created`, `Detailed Type`, `Group`, `Location`, `MIME Type`, `Octal Permissions`, `Owner`, `Permissions`, `SELinux Context` y `Modified - Time`.
- [x] Los iconos de archivo se muestran solo en la columna `Name`, no en las demás columnas.
- [x] Menú contextual moderno superior con acciones `Cut`, `Copy`, `Paste`, `Rename`, `Share` y `Delete`.
- [x] Opción en Preferencias para activar o desactivar el menú contextual moderno.
- [x] Corrección del estado inicial para que `Paste` aparezca deshabilitado si no hay nada en el portapapeles.
- [x] Carga de configuración robusta con backfill automático de claves nuevas en configuraciones antiguas.
- [x] Vista previa lateral de imágenes corregida usando `QImageReader` en segundo plano y `QPixmap` solo en el hilo UI.
- [x] Soporte de vista previa lateral para una imagen seleccionada.
- [x] Soporte de galería de imágenes en el panel lateral para carpetas con varias imágenes.
- [x] Miniaturas de imágenes directamente en el área principal del gestor, independientes del panel lateral.
- [x] Miniaturas visibles en `Icons`, `List`, `Details` y `Compact`.
- [x] Caché de miniaturas para formatos `png`, `jpg`, `jpeg`, `gif`, `bmp`, `svg` y `webp`.

## Decisiones técnicas importantes ya tomadas

- No se usarán iconos Tabler embebidos como fuente principal.
- El programa debe usar los iconos del sistema para respetar el tema activo del usuario.
- Para cambiar el tema de iconos en entornos Qt, el usuario puede necesitar `qt6ct`.
- El almacenamiento de configuración/datos relevante está en:
  - `~/.local/share/linux-file-manager/`
- Durante desarrollo, a veces conviene borrar esa carpeta para forzar que aparezcan nuevos valores por defecto si una config vieja los oculta.
- El proyecto apunta a cumplir políticas Debian, por lo que hay que evitar conflictos de nombres, revisar licencias y cuidar dependencias.

## Archivos clave para continuar

### Núcleo de configuración y rutas

- `lfmapp/core/config.py`
- `lfmapp/core/paths.py`
- `lfmapp/core/app_data.py`

### UI principal

- `lfmapp/ui/main_window.py`
- `lfmapp/ui/workspace.py`
- `lfmapp/ui/sidebar.py`
- `lfmapp/ui/preview_panel.py`
- `lfmapp/ui/preferences_dialog.py`

### Modelo de archivos y miniaturas

- `lfmapp/models/file_system_model.py`
- `lfmapp/services/preview_worker.py`

### Documentación y planificación

- `README.md`
- `ROADMAP.md`

## Qué revisar primero después del formateo

1. Restaurar el repositorio y abrir este archivo.
2. Ejecutar el proyecto y comprobar que arranca con la configuración recreada automáticamente.
3. Verificar visualmente:
   - Sidebar por pestañas
   - Menú contextual moderno
   - Respeto del terminal configurado
   - Miniaturas de imágenes en las cuatro vistas
   - XDG User Directories en `Quick Access`
4. Si algo “no refleja” cambios recientes, borrar:
   - `~/.local/share/linux-file-manager/`
5. Ejecutar la batería mínima de pruebas.

## Pruebas mínimas recomendadas al retomar

- `pytest -q tests/test_file_system_model.py`
- `pytest -q tests/test_preview_worker.py`
- `pytest -q tests/test_main_window.py`
- `python3 -m compileall lfmapp`

## Objetivo estratégico de producto

El proyecto ya puede describirse como un gestor de archivos Linux funcional, práctico y bien integrado con la plataforma. La siguiente etapa no consiste simplemente en añadir más funciones, sino en transformar esa base en una experiencia de productividad rápida, fiable, coherente y agradable.

La visión de producto es:

> Crear el mejor gestor de archivos Linux enfocado en productividad: rápido con teclado y ratón, seguro en operaciones delicadas, capaz en flujos por lotes, poco intrusivo y sostenible a nivel de arquitectura.

Toda nueva función debe mejorar al menos uno de estos cinco resultados:

1. Reducir tiempo, clics o pulsaciones para completar tareas frecuentes.
2. Evitar errores o pérdida de contexto durante operaciones de archivos.
3. Mantener acciones y comportamientos consistentes en todas las vistas.
4. Sustituir modales innecesarios por interacción en línea y feedback persistente.
5. Disminuir el acoplamiento técnico para que el proyecto pueda crecer sin degradarse.

## Criterios globales de éxito

La visión se considerará alcanzada cuando el programa cumpla, como mínimo, estos criterios:

- Las operaciones habituales pueden completarse completamente con teclado.
- Copiar o mover cientos de archivos no bloquea la interfaz y ofrece pausa, cancelación, reintento e historial.
- Los conflictos de nombres se resuelven de manera predecible, con vista previa y reglas de “aplicar a todos”.
- La búsqueda muestra resultados progresivos y permite guardar y reutilizar filtros.
- El renombrado masivo incluye vista previa, validación y deshacer.
- La selección múltiple y las acciones por lote son visibles, coherentes y reversibles cuando sea posible.
- La mayoría de mensajes no críticos aparecen en barras, banners, paneles o notificaciones no modales.
- El foco, la selección, la posición de desplazamiento y el historial se conservan al cambiar de vista o actualizar una carpeta.
- Las funciones clave poseen pruebas unitarias, de integración y GUI.
- `MainWindow` deja de ser el centro de toda la lógica y funciona principalmente como compositor de componentes.

## Reglas de ejecución para agentes

Cada tarea de este roadmap debe realizarse con estas reglas:

1. Leer primero `ROADMAP.md`,`README.md` y las pruebas relacionadas.
2. No introducir lógica de negocio nueva directamente en `MainWindow` salvo cableado mínimo.
3. Separar en cada cambio: modelo/servicio, controlador o coordinador, widget y pruebas.
4. Mantener compatibilidad con Debian, X11 y Wayland, salvo que una tarea documente una limitación explícita.
5. Respetar los iconos del tema mediante `QIcon.fromTheme()` y fallbacks centralizados.
6. No bloquear el hilo de interfaz con E/S, indexación, miniaturas u operaciones largas.
7. Añadir criterios de aceptación automatizados y una lista breve de pruebas manuales.
8. Mantener traducciones preparadas para español e inglés; no introducir textos visibles sin `tr()`.
9. No eliminar una función existente sin migración, reemplazo documentado o prueba que justifique el cambio.
10. Actualizar este roadmap al terminar una tarea, incluyendo archivos modificados, pruebas y limitaciones conocidas.

## Orden recomendado de implementación

No ejecutar todas las iniciativas a la vez. Seguir este orden:

1. Fundamentos de arquitectura, acciones y estado de UI.
2. Motor fiable de operaciones y resolución de conflictos.
3. Productividad por teclado y paleta de comandos.
4. Búsqueda, filtrado y selección avanzada.
5. Flujos por lotes.
6. Pulido visual, accesibilidad y reducción de modales.
7. Rendimiento, compatibilidad y preparación de lanzamiento.

---

# Fase 0 — Línea base, métricas y protección contra regresiones

## 0.1 Inventario funcional y mapa de flujos

- [ ] Documentar los flujos actuales de navegación, selección, copiar, mover, pegar, eliminar, renombrar, buscar y previsualizar.
- [ ] Crear una matriz que indique qué acciones existen en menú, toolbar, menú contextual, atajo y paleta de comandos.
- [ ] Identificar comportamientos distintos entre `Icons`, `List`, `Details` y `Compact`.
- [ ] Registrar modales existentes y clasificarlos como imprescindibles, reemplazables o eliminables.

**Entregable:** `docs/ux-flow-audit.md`.

**Criterios de aceptación:**

- Cada acción principal tiene un único identificador lógico.
- Toda inconsistencia conocida queda convertida en tarea concreta.
- El documento incluye capturas o descripciones reproducibles de los problemas.

## 0.2 Métricas de experiencia y rendimiento

- [ ] Medir tiempo de arranque en frío y caliente.
- [ ] Medir apertura de carpetas con 100, 1.000 y 10.000 entradas.
- [ ] Medir tiempo hasta el primer resultado de búsqueda.
- [ ] Medir consumo de memoria durante miniaturas y operaciones largas.
- [ ] Definir presupuestos de rendimiento y registrar una línea base.

**Entregable:** `docs/performance-baseline.md` y scripts reproducibles en `scripts/`.

## 0.3 Pruebas de flujos críticos

- [ ] Añadir pruebas GUI para navegación, selección, cambio de vista, copiar/pegar, conflicto, cancelar operación, renombrar y búsqueda.
- [ ] Añadir fixtures con árboles de archivos temporales y casos de permisos, enlaces simbólicos y nombres Unicode.
- [ ] Verificar que una operación cancelada no deje archivos parciales sin registrar.

---

# Fase 1 — Arquitectura modular y sistema unificado de acciones

## 1.1 Reducir responsabilidades de `MainWindow`

Situación actual comprobada: `lfmapp/ui/main_window.py` supera las 3.200 líneas. Debe convertirse progresivamente en un compositor y coordinador de alto nivel.

- [ ] Crear `lfmapp/controllers/` o un paquete equivalente.
- [ ] Extraer `NavigationController` para rutas, historial, atrás, adelante, subir y refrescar.
- [ ] Extraer `SelectionController` para selección actual, selección múltiple y estado derivado.
- [ ] Extraer `FileActionController` para abrir, copiar, cortar, pegar, renombrar, papelera y eliminar.
- [ ] Extraer `ViewController` para cambio de vista, zoom, columnas y persistencia visual.
- [ ] Extraer `SearchController` para consultas, filtros, cancelación y resultados.
- [ ] Extraer `PreviewController` para ciclo de vida de la vista previa.
- [ ] Extraer `OperationCenterController` para cola, progreso, errores e historial.
- [ ] Mover construcción de menús y toolbars a componentes o factories declarativas.

**Criterios de aceptación:**

- `MainWindow` no contiene algoritmos de copia, búsqueda, filtrado, resolución de conflictos ni miniaturas.
- Los controladores pueden probarse sin mostrar toda la ventana principal.
- No existen conexiones de señales duplicadas al cambiar de workspace o recrear widgets.
- Meta inicial: reducir `main_window.py` por debajo de 1.500 líneas; meta final: por debajo de 900, sin dividir artificialmente código sin cohesión.

## 1.2 Registro central de acciones

- [ ] Crear un `ActionRegistry` con identificadores estables, texto traducible, icono, atajo, estado habilitado y callback.
- [ ] Hacer que menú, toolbar, menú contextual y paleta reutilicen las mismas `QAction` o definiciones.
- [ ] Centralizar las condiciones de habilitación según selección, portapapeles, permisos, vista y operación activa.
- [ ] Evitar acciones duplicadas con estados contradictorios.
- [ ] Permitir al usuario consultar y personalizar atajos sin crear colisiones silenciosas.

**Criterios de aceptación:**

- “Rename”, “Delete”, “Paste” y demás acciones muestran el mismo estado en todas las superficies.
- Cambiar un atajo se refleja sin reiniciar cuando sea técnicamente seguro.
- Las colisiones de atajos se detectan y explican claramente.

### 1.2.1 Filtrado, búsqueda y selección
- [ ] Definir un estado unificado de filtrado rápido y búsqueda estructurada que sea compartido por barra de filtro, campo de filtro permanente y el menú de búsqueda.
- [ ] El filtro rápido debe poder activarse con una tecla, actualizar la vista inmediatamente, mostrar el número de elementos ocultos y poder borrarse con `Esc`.
- [ ] Implementar un modo "Mostrar todo" que desactive temporalmente los filtros del panel actual sin perder la configuración de filtrado subyacente.
- [ ] Soportar un campo de filtro persistente opcional en la barra con historial y menú de filtros, que controle el mismo estado que la barra de filtro emergente.
- [ ] Soportar opciones de filtrado avanzadas: coincidencia parcial, ignorar diacríticos, modo "any word", expresiones regulares y condiciones complejas tipo evaluador.
- [ ] El estado de selección debe ser central, con recuentos claros y comandos de selección automáticos por patrón, extensión, duplicados, carpetas vacías y similares.
- [ ] Definir estado de origen/destino para operaciones de copia/movido en paneles duales y en modo único, de modo que el flujo no dependa de una vista principal única.
- [ ] El modelo de acciones debe exponer la primera clase el origen/destino activo, de modo que Copy/Move/Paste puedan decidir su objetivo sin lógica dispersa.
- [ ] El controlador de vistas debe permitir ordenación y agrupación por múltiples campos, con soporte para campos no visibles y cambio de dirección por teclas modificadoras.

## 1.3 Modelo explícito de estado de interfaz

- [ ] Definir un estado observable para ruta, selección, vista, búsqueda, preview y operaciones.
- [ ] Evitar que widgets consulten directamente múltiples servicios para reconstruir el mismo estado.
- [ ] Conservar foco, selección y scroll al refrescar o cambiar de vista.

---

# Fase 2 — Operaciones de archivos fiables y centro de actividad

## 2.1 Motor de operaciones asíncronas

- [ ] Convertir copiar, mover, eliminar, restaurar y extraer en trabajos de una cola común.
- [ ] Exponer estados: pendiente, preparando, ejecutando, pausado, cancelando, completado, fallido y completado con advertencias.
- [ ] Añadir pausa y reanudación reales donde el backend lo permita.
- [ ] Añadir cancelación cooperativa y limpieza segura de archivos parciales.
- [ ] Añadir reintento de una operación completa o solo de elementos fallidos.
- [ ] Calcular progreso por bytes y por elementos, velocidad y tiempo estimado sin bloquear la UI.
- [ ] Limitar concurrencia para evitar saturar disco o red.
- [ ] Registrar origen, destino, decisiones de conflicto, errores y resultado.

## 2.2 Centro de operaciones no modal

- [ ] Crear un panel desplegable o inferior persistente para operaciones activas y recientes.
- [ ] Mostrar progreso agregado y detalle por trabajo.
- [ ] Permitir pausar, continuar, cancelar, reintentar, ocultar y limpiar completadas.
- [ ] Permitir abrir ubicación de origen o destino desde una operación.
- [ ] Mantener notificaciones discretas al completar, fallar o requerir intervención.
- [ ] No usar un diálogo modal de progreso como interfaz principal.

**Criterios de aceptación:**

- El usuario puede continuar navegando mientras se copian archivos.
- Cerrar el panel no cancela la operación.
- Un error individual no oculta el resultado del resto del lote.
- La interfaz sigue respondiendo con operaciones de varios gigabytes simuladas.

## 2.3 Historial, deshacer y repetición

- [ ] Integrar la cola con `operation_history.py`.
- [ ] Definir qué operaciones son reversibles y bajo qué condiciones.
- [ ] Implementar deshacer para renombrar, mover, crear, enviar a papelera y restaurar cuando sea seguro.
- [ ] Mostrar claramente cuándo una operación no puede deshacerse.
- [ ] Permitir repetir operaciones fallidas o recurrentes con revisión previa.

---

# Fase 3 — Resolución robusta de conflictos

## 3.1 Modelo de conflicto

- [ ] Crear objetos de conflicto independientes de la UI con origen, destino, tipo, tamaño, fechas, permisos y checksum opcional.
- [ ] Soportar conflictos archivo–archivo, carpeta–carpeta, archivo–carpeta y destino no escribible.
- [ ] Separar decisiones de reemplazo, omisión, renombrado, combinación de carpetas y conservación de ambos.

## 3.2 Interfaz de conflictos productiva

- [ ] Mostrar comparación clara de origen y destino.
- [ ] Ofrecer `Replace`, `Skip`, `Keep Both`, `Rename`, `Merge` y `Cancel` solo cuando correspondan.
- [ ] Añadir “aplicar a todos los conflictos restantes” con alcance explícito.
- [ ] Permitir reglas por condición: más nuevo, más grande, mismo tamaño, misma fecha o mismo contenido.
- [ ] Mostrar vista previa del nombre generado para “Keep Both”.
- [ ] Permitir revisar una cola de conflictos antes de confirmar en lotes grandes.
- [ ] Recordar decisiones solo durante la operación actual, salvo preferencia explícita del usuario.

**Criterios de aceptación:**

- Nunca se sobrescribe un archivo sin decisión explícita o regla visible.
- “Aplicar a todos” indica exactamente a qué tipos de conflicto afecta.
- Cancelar desde el diálogo devuelve el control al centro de operaciones sin congelar la aplicación.
- Todas las decisiones quedan registradas en el historial de la operación.

---

# Fase 4 — Productividad por teclado y comandos rápidos

## 4.1 Navegación completa por teclado

- [ ] Auditar orden de foco y foco inicial en cada vista y diálogo.
- [ ] Implementar atajos consistentes para barra de ubicación, sidebar, vista, preview, operaciones y búsqueda.
- [ ] Permitir cambiar de panel sin perder selección.
- [ ] Añadir selección por teclado: rango, alternancia, seleccionar por patrón, invertir y restaurar selección.
- [ ] Asegurar que `Enter`, `Space`, `F2`, `Delete`, `Shift+Delete`, `Ctrl+L`, `Ctrl+F`, `Ctrl+H` y teclas de navegación tengan semántica consistente.
- [ ] Añadir navegación tipo “type-ahead”: escribir selecciona rápidamente por nombre.

## 4.2 Paleta de comandos

- [ ] Añadir una paleta invocable por atajo configurable.
- [ ] Buscar acciones por nombre, alias y palabras clave traducidas.
- [ ] Mostrar atajo actual, icono y motivo de deshabilitación.
- [ ] Incluir acciones contextuales según selección y ruta.
- [ ] Registrar comandos recientes y favoritos sin mezclar datos sensibles.
- [ ] Permitir comandos de navegación: ir a ruta, abrir reciente, cambiar vista y alternar paneles.

## 4.3 Quick actions y menú contextual coherente

- [ ] Reducir el menú contextual a acciones relevantes y mover acciones secundarias a submenús claros.
- [ ] Hacer configurable la fila de acciones rápidas.
- [ ] Evitar que una misma operación se nombre o comporte distinto según la vista.
- [ ] Mostrar feedback inmediato al ejecutar acciones sin resultado visual obvio.

---

# Fase 5 — Búsqueda y filtrado de nivel productivo

## 5.1 Búsqueda instantánea y cancelable

- [ ] Separar búsqueda por nombre, contenido y metadatos.
- [ ] Emitir resultados progresivos en lotes pequeños.
- [ ] Cancelar consultas anteriores al escribir una nueva.
- [ ] Evitar que resultados tardíos sobrescriban una consulta más reciente.
- [ ] Mostrar alcance, tiempo, cantidad de resultados y estado de indexación.
- [ ] Permitir buscar en carpeta actual, subcarpetas, ubicaciones elegidas o “This Computer”.

## 5.2 Filtros potentes

- [ ] Añadir filtros combinables por tipo, extensión, tamaño, fecha, propietario, permisos, etiquetas, ocultos y contenido.
- [ ] Incluir operadores comprensibles: es, no es, contiene, empieza por, mayor que, menor que, antes de y después de.
- [ ] Mostrar los filtros activos como chips removibles en la interfaz.
- [ ] Permitir editar filtros sin reabrir un diálogo modal complejo.
- [ ] Permitir guardar búsquedas con nombre, alcance y orden.
- [ ] Añadir búsquedas guardadas al sidebar o a una sección dedicada.
- [ ] Serializar filtros con versión para permitir futuras migraciones.

## 5.3 Resultados como espacio de trabajo

- [ ] Permitir abrir ubicación contenedora sin perder los resultados.
- [ ] Permitir copiar, mover, renombrar, etiquetar y eliminar desde resultados.
- [ ] Agrupar por carpeta, tipo, fecha o etiqueta.
- [ ] Resaltar coincidencias sin alterar el nombre real.
- [ ] Conservar la consulta al volver atrás.

**Criterios de aceptación:**

- Primeros resultados visibles rápidamente en árboles grandes.
- Los filtros guardados sobreviven reinicios y migraciones de configuración.
- Todas las acciones sobre resultados usan los mismos controladores y reglas de conflicto que la vista normal.

---

# Fase 6 — Selección avanzada y flujos por lotes

## 6.1 Selección avanzada

- [ ] Seleccionar por patrón glob, expresión regular opcional, extensión, tipo, tamaño y fecha.
- [ ] Invertir, guardar, restaurar y nombrar conjuntos de selección temporales.
- [ ] Mostrar una barra de selección con cantidad, tamaño total y acciones relevantes.
- [ ] Mantener selección al ordenar o cambiar de vista cuando los elementos sigan presentes.
- [ ] Evitar selecciones invisibles o ambiguas tras filtrar.

## 6.2 Renombrado masivo

- [ ] Crear un flujo de renombrado masivo no destructivo con tabla “antes/después”.
- [ ] Soportar prefijo, sufijo, reemplazo, numeración, mayúsculas/minúsculas, fecha y expresiones regulares opcionales.
- [ ] Permitir reordenar reglas y activar/desactivar cada transformación.
- [ ] Detectar nombres vacíos, duplicados, reservados, demasiado largos o inválidos antes de ejecutar.
- [ ] Resaltar conflictos y ofrecer corrección automática.
- [ ] Ejecutar como una única operación registrable y reversible.
- [ ] Incluir presets guardables y ejemplos en vivo.

## 6.3 Otras acciones por lote

- [ ] Crear carpetas o archivos múltiples desde patrón.
- [ ] Cambiar permisos y propietario con advertencias claras.
- [ ] Aplicar etiquetas a grupos.
- [ ] Comprimir, extraer o calcular checksum por lote.
- [ ] Abrir con una aplicación elegida o ejecutar una acción personalizada segura.

---

# Fase 7 — UI pulida, consistente y menos modal

## 7.1 Sistema visual y componentes reutilizables

- [ ] Definir tamaños, márgenes, densidad, iconos, estados hover/focus/disabled y jerarquía tipográfica.
- [ ] Crear componentes comunes para banners, mensajes vacíos, errores, barras de selección, chips y filas de progreso.
- [ ] Eliminar estilos locales contradictorios y respetar el tema Qt del sistema.
- [ ] Probar temas claros, oscuros y de alto contraste.
- [ ] Auditar textos truncados, tooltips, espaciado y escalado HiDPI.

## 7.2 Reducción de modales

- [ ] Sustituir confirmaciones informativas por undo banners cuando la operación sea reversible.
- [ ] Usar banners en línea para errores recuperables y problemas de permisos.
- [ ] Reservar modales para decisiones destructivas, conflictos complejos o entrada imprescindible.
- [ ] Mantener mensajes accesibles el tiempo suficiente y permitir revisarlos en un centro de actividad.

## 7.3 Persistencia de contexto

- [ ] Persistir por carpeta: vista, zoom, columnas visibles, orden, ancho y criterio de ordenación.
- [ ] Restaurar pestañas o espacios de trabajo según preferencia.
- [ ] Mantener selección y scroll al refrescar.
- [ ] No saltar automáticamente a otra carpeta tras una operación salvo acción explícita.

## 7.4 Estados vacíos y errores útiles

- [ ] Diseñar estados vacíos para carpetas, resultados, red, bookmarks y recientes.
- [ ] Explicar errores con causa, efecto y acción recomendada.
- [ ] Añadir botones contextuales: reintentar, autenticar, abrir permisos, mostrar detalles o copiar diagnóstico.

---

# Fase 8 — Accesibilidad

- [ ] Definir nombres, descripciones y roles accesibles para controles personalizados.
- [ ] Asegurar indicadores de foco visibles en todos los temas.
- [ ] No comunicar estado únicamente mediante color.
- [ ] Revisar contraste y tamaños mínimos.
- [ ] Probar navegación completa sin ratón.
- [ ] Probar con lector de pantalla disponible en Linux, por ejemplo Orca.
- [ ] Anunciar inicio, progreso, conflicto, finalización y fallo de operaciones sin generar ruido excesivo.
- [ ] Respetar preferencias de reducción de animación cuando estén disponibles.
- [ ] Documentar atajos en una vista accesible y buscable.

**Criterios de aceptación:**

- Los flujos críticos pueden completarse con lector de pantalla y teclado.
- Ningún diálogo atrapa el foco sin salida clara.
- Los controles de solo icono poseen nombre accesible y tooltip traducido.

---

# Fase 9 — Rendimiento, miniaturas y escalabilidad

## 9.1 Pipeline de miniaturas

- [ ] Implementar pool de workers limitado y priorizado por elementos visibles.
- [ ] Cancelar solicitudes al salir de carpeta o cambiar de vista.
- [ ] Añadir caché en disco versionada, con límites de tamaño y limpieza.
- [ ] Evitar regenerar miniaturas cuando archivo y parámetros no cambiaron.
- [ ] Añadir soporte progresivo para vídeo, PDF y documentos mediante backends opcionales seguros.
- [ ] Respetar configuraciones de privacidad, unidades remotas y tamaños máximos.

## 9.2 Carpetas grandes

- [ ] Cargar entradas por lotes y mantener la UI interactiva.
- [ ] Evitar ordenar o calcular metadatos costosos en el hilo principal.
- [ ] Diferir columnas costosas hasta que sean visibles o solicitadas.
- [ ] Probar con 10.000, 100.000 y más entradas mediante simulación.

## 9.3 Búsqueda e indexación

- [ ] Definir límites de CPU, memoria e I/O.
- [ ] Pausar o reducir prioridad cuando el sistema está bajo carga.
- [ ] Excluir rutas configurables y respetar montajes remotos.
- [ ] Ofrecer estado y control de indexación sin depender de terminal.

---

# Fase 10 — Integración Linux, red y compatibilidad

- [ ] Mejorar compatibilidad X11/Wayland para drag and drop, portapapeles, activación de ventanas y posicionamiento.
- [ ] Probar XFCE, KDE Plasma, GNOME, LXQt, Fluxbox y entornos mínimos cuando sea posible.
- [ ] Mantener integración XDG para carpetas, MIME, aplicaciones predeterminadas, papelera y portales.
- [ ] Implementar SFTP detrás de una interfaz de proveedores remotos, sin acoplarlo a la UI.
- [ ] Diseñar manejo de credenciales mediante servicios seguros del escritorio; no guardar contraseñas en texto plano.
- [ ] Tratar operaciones remotas con la misma cola, progreso, cancelación y conflictos que las locales.
- [ ] Añadir estados claros para desconexión, reconexión y autenticación expirada.

---

# Fase 11 — Calidad, telemetría local y diagnóstico

- [ ] Añadir logging estructurado con niveles y rotación.
- [ ] Crear una acción “Copy Diagnostic Information” que excluya rutas o datos privados salvo consentimiento explícito.
- [ ] Añadir un modo de diagnóstico para señales, operaciones, miniaturas y búsqueda.
- [ ] Mantener la telemetría desactivada; cualquier métrica debe ser local salvo decisión futura explícita y transparente.
- [ ] Añadir pruebas de migración de configuración y bases de datos.
- [ ] Añadir pruebas de fallos: disco lleno, permisos, desconexión, destino eliminado y archivo cambiado durante la operación.
- [ ] Ejecutar pruebas estáticas, unitarias, integración, GUI y empaquetado en CI.

---

# Fase 12 — Debian, distribución y lanzamiento

- [ ] Revisar dependencias reales y separar obligatorias, recomendadas y opcionales.
- [ ] Confirmar estrategia de `qt6ct` en documentación y metadatos, sin imponerlo cuando el entorno ya gestiona Qt.
- [ ] Auditar todos los nombres de iconos y fallbacks en `lfmapp/ui/icons.py`.
- [ ] Revisar licencias, copyright, AppStream, desktop file y manpage.
- [ ] Validar con `lintian`, pruebas de instalación limpia y actualización desde versión anterior.
- [ ] Añadir checklist de release, versionado, changelog y notas de migración.
- [ ] Crear CI para paquete fuente y binario Debian en entornos compatibles.
- [ ] Documentar claramente funciones opcionales y dependencias externas para previews, red o extracción.

---

# Backlog priorizado inmediato

Estas tareas deben abordarse primero porque desbloquean el resto del roadmap.

## Prioridad P0 — Fundamentos

- [ ] Crear la auditoría de acciones y flujos (`docs/ux-flow-audit.md`).
- [ ] Implementar `ActionRegistry` y migrar al menos navegación, clipboard, rename y delete.
- [ ] Extraer `NavigationController`, `SelectionController` y `FileActionController` de `MainWindow`.
- [ ] Auditar Quick Access, bookmarks/favorites, aliases y recientes para integrarlos con la paleta de comandos y la barra de ruta.
- [ ] Auditar la arquitectura del panel utilitario y la visualización de resultados de búsqueda como colecciones virtuales.
- [ ] Definir contrato y estados del motor de operaciones.
- [ ] Añadir pruebas GUI para copiar/mover y conservación de selección.

## Prioridad P1 — Mayor impacto para el usuario

- [ ] Centro de operaciones no modal con cancelar y reintentar.
- [ ] Diálogo de conflictos con `Replace`, `Skip`, `Keep Both`, `Rename` y “Apply to all”.
- [ ] Paleta de comandos y mapa consistente de atajos.
- [ ] Búsqueda progresiva con filtros visibles y cancelación de consultas obsoletas.
- [ ] Renombrado masivo con vista previa y validación.

## Prioridad P2 — Refinamiento competitivo

- [ ] Persistencia visual por carpeta.
- [ ] Selección avanzada y barra de acciones por lote.
- [ ] Auditoría de modales y sustitución por banners/undo.
- [ ] Accesibilidad completa por teclado y lector de pantalla.
- [ ] Caché de miniaturas en disco y priorización por viewport.

## Prioridad P3 — Expansión

- [ ] SFTP y proveedores remotos.
- [ ] Terminal integrada opcional, desacoplada del terminal externo.
- [ ] Previews de vídeo/PDF/documentos con backends opcionales.
- [ ] Workspaces y búsquedas guardadas avanzadas.

---

# Definición de terminado para cada iniciativa

Una iniciativa no debe marcarse como completada hasta cumplir todo lo siguiente:

- [ ] Código dividido de acuerdo con responsabilidades claras.
- [ ] Textos visibles traducibles.
- [ ] Atajos, menú, toolbar, contexto y paleta coherentes cuando corresponda.
- [ ] Pruebas unitarias para lógica y pruebas GUI para el flujo principal.
- [ ] Prueba manual documentada en al menos X11 y Wayland cuando la función dependa del compositor.
- [ ] Manejo de errores y cancelación definido.
- [ ] Sin bloqueo perceptible del hilo principal.
- [ ] Configuración migrable y valores por defecto seguros.
- [ ] Documentación actualizada.
- [ ] Sin regresiones en las pruebas existentes.

# Riesgos y restricciones conocidas

- La configuración persistida puede ocultar cambios recientes si no existe una migración adecuada; dejar de depender de borrar manualmente el directorio de datos como solución habitual.
- Los entornos de escritorio, temas de iconos, gestores de ventanas y terminales producen comportamientos distintos.
- Wayland restringe algunas capacidades históricamente disponibles en X11; usar APIs y portales apropiados.
- Pausar o reanudar ciertas operaciones puede no ser atómico; la UI debe representar las limitaciones honestamente.
- Deshacer operaciones remotas, sobrescrituras o eliminaciones permanentes puede ser imposible; nunca prometer reversibilidad inexistente.
- Checksums automáticos en conflictos pueden ser costosos; ofrecerlos de forma selectiva o diferida.
- Una arquitectura excesivamente fragmentada también perjudica el mantenimiento; extraer módulos por cohesión, no solo para reducir líneas.

# Estado de documentación

- `README.md` contiene información sobre configuración y reinicio de datos.
- `ROADMAP.md` es la fuente principal de dirección estratégica, prioridades y criterios de aceptación.
- Las decisiones arquitectónicas importantes deben registrarse en `docs/adr/` mediante ADR breves.

# Instrucción para la próxima sesión o agente

Leer en este orden:

1. `ROADMAP.md`
2. `README.md`
3. `docs/ux-flow-audit.md`, cuando exista
4. ADR relevantes en `docs/adr/`

Después revisar:

1. `lfmapp/ui/main_window.py`
2. `lfmapp/ui/workspace.py`
3. `lfmapp/services/file_operations.py`
4. `lfmapp/services/operation_queue.py`
5. `lfmapp/services/operation_history.py`
6. `lfmapp/services/search_service.py`
7. `lfmapp/models/file_system_model.py`
8. las pruebas relacionadas

El primer agente debe comenzar por Fase 0 y Fase 1. No debe intentar implementar simultáneamente búsqueda avanzada, SFTP y renombrado masivo antes de estabilizar acciones, controladores y operaciones.
