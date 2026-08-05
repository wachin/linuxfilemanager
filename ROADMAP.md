# ROADMAP.md — Linux File Manager

Última actualización: 2026-07-27

Este archivo queda preparado para continuar el desarrollo después de formatear el ordenador. Resume el estado real del proyecto, lo ya conseguido, lo pendiente y dónde mirar primero.

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

## Estado actual resumido

El proyecto ya tiene una base funcional amplia. No está en fase inicial. Ya existen:

- Ventana principal con barra de menú, barra de herramientas, barra de estado y paneles.
- Sidebar por pestañas con `Quick Access`, `This Computer`, `Network`, `Bookmarks` y `Recents`.
- Navegación por historial y barra de dirección editable.
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
- `TODOS.md`
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

## Pendientes prioritarios reales

Estos son los siguientes trabajos con mejor relación impacto/esfuerzo.

### Visión de productividad

El objetivo siguiente es convertir `linux-file-manager` en una herramienta que ayude al usuario a moverse, organizar y actuar sobre archivos sin interrumpir el flujo.
Las decisiones deben buscar:

- minimizar clics y pantalla completa innecesaria,
- mantener el contexto visible y accesible,
- ofrecer atajos que sustituyan tareas repetitivas,
- dar retroalimentación inmediata en operaciones largas,
- hacer que las acciones frecuentes estén a un paso.

### Prioridad alta

- [ ] Auditoría completa de nombres de iconos de sistema usados con `QIcon.fromTheme()`.
- [ ] Persistencia por carpeta de columnas visibles, orden y ancho en `Details`.
- [ ] Mejor diálogo de conflictos para copiar/mover: reemplazar, omitir, renombrar, aplicar a todo.
- [ ] Revisión de acciones por tipo de archivo para que archivos, carpetas, imágenes, documentos y comprimidos sean consistentes.
- [ ] Implementar atajos clave y comandos rápidos para mover/abrir/renombrar sin tocar el ratón.
- [ ] Añadir un panel de progreso de operaciones con acciones rápidas para pausar, cancelar y repetir.
- [ ] Flujo de búsqueda/filter mejorado con acceso rápido por palabra clave y filtros guardados.
- [ ] Añadir más pruebas GUI de flujos comunes.
- [ ] Añadir preferencia de vista rápida para alternar entre `Details` y `Compact` sin perder selección.

### Prioridad media

- [ ] Acción para restaurar carpetas por defecto en `Quick Access` si el usuario las elimina.
- [ ] Flujo de renombrado masivo con vista previa.
- [ ] Mejoras adicionales del flujo de terminal y posible panel integrado opcional.
- [ ] Conectores remotos empezando por `SFTP`.
- [ ] Mejoras de accesibilidad y navegación por teclado.

### Prioridad de ingeniería

- [ ] Sistema de miniaturas más avanzado: pool de workers, caché en disco y soporte ampliado para vídeo/documentos.
- [ ] Cola de operaciones asíncronas con reintentos, reanudación y mejor feedback.
- [ ] Seguir dividiendo `MainWindow` en controladores/componentes más pequeños.
- [ ] Mejor compatibilidad entre X11 y Wayland, especialmente en drag and drop.

### Prioridad Debian/empaquetado

- [ ] Revisar dependencias reales para empaquetado.
- [ ] Confirmar estrategia de `qt6ct` dentro de la documentación o dependencias recomendadas.
- [ ] Auditar nombres de iconos del sistema y añadir fallback de tema/icon names en `lfmapp/ui/icons.py`.
- [ ] Revisar licencias y metadatos para publicación limpia.
- [ ] Añadir checklist de release pública.
- [ ] Añadir CI para pruebas y validación de empaquetado.

## Riesgos o puntos delicados conocidos

- La configuración persistida puede ocultar cambios recientes del código si no se limpia el directorio de datos del usuario.
- Algunas diferencias de comportamiento dependen del entorno de escritorio, del tema de iconos y de la terminal instalada.
- El sistema de miniaturas ya funciona, pero todavía no es un thumbnailer completo con caché en disco y pipeline asíncrono amplio.
- `MainWindow` sigue siendo grande; conviene seguir separándolo para mantener el proyecto sostenible.

## Estado de documentación

- `README.md` ya contiene información sobre dónde se guarda la configuración y cómo resetearla.
- `TODOS.md` ya incluye una sección de logros completados y pendientes futuros.
- Este `ROADMAP.md` queda como documento principal de continuidad después del formateo.

## Instrucción para la próxima sesión

Al retomar el proyecto, empezar por leer:

1. `ROADMAP.md`
2. `TODOS.md`
3. `README.md`

Después, revisar:

1. `lfmapp/ui/main_window.py`
2. `lfmapp/ui/workspace.py`
3. `lfmapp/models/file_system_model.py`
4. `lfmapp/services/preview_worker.py`

Eso devuelve contexto suficiente para continuar sin este chat.
