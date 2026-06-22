Tabler SVG assets copied into Linux File Manager for runtime use belong here.

Development workflow:

1. Keep `third-party/tabler-icons` as the upstream development source.
2. Use `scripts/import_tabler_icon.py` to copy only the icons the app needs.
3. Load runtime icons from `lfmapp/assets/icons/tabler/`, not from the Git submodule.

The `outline/` and `filled/` subdirectories are created on demand by the import script.
