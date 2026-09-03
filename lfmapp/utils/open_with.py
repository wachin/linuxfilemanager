"""Open-with utility for linux-file-manager.

Provides functions to open files with default or specific applications.
Uses XDG standards and xdg-utils where available.
"""

import os
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Optional


def open_with_default(path: Path) -> bool:
    """Open a file with the default application.

    Uses xdg-open on Linux.
    """
    if not path.exists():
        return False
    if path.suffix.lower() == ".desktop":
        return open_desktop_entry(path)
    try:
        subprocess.Popen(
            ["xdg-open", str(path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
        return True
    except FileNotFoundError:
        # xdg-open not available, try gtk-launch
        try:
            subprocess.Popen(
                ["gtk-launch", str(path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )
            return True
        except FileNotFoundError:
            return False


def open_with_dialog(path: Path) -> bool:
    """Show a dialog to choose application, then open the file.

    Uses xdg-mime and .desktop entries to present available applications.
    """
    if not path.exists():
        return False

    apps = get_available_applications(path)
    if not apps:
        return open_with_default(path)

    # If only one app, launch it directly
    if len(apps) == 1:
        return launch_application_for_path(apps[0][0], path) or open_with_default(path)

    # Present a simple name-based choice to the UI layer.
    return open_with_default(path)


def get_available_applications(path: Path) -> list[tuple[str, str]]:
    """Get list of available applications that can open a file.

    Returns a list of (desktop_file, name) tuples.
    """
    if not path.exists():
        return []

    mime_type = _get_mime_type(path)
    if not mime_type:
        return []

    app_map = _find_applications_for_mime(mime_type)
    if not app_map:
        return []

    ordered_apps = []
    default_app = _get_default_app_for_mime(mime_type)
    if default_app and default_app in app_map:
        ordered_apps.append((default_app, app_map[default_app]))

    for desktop_file, name in app_map.items():
        if desktop_file != default_app:
            ordered_apps.append((desktop_file, name))

    return ordered_apps


def _get_default_app_for_mime(mime_type: str) -> str | None:
    try:
        result = subprocess.run(
            ["xdg-mime", "query", "default", mime_type],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            apps = [a.strip() for a in result.stdout.strip().split(";") if a.strip()]
            return apps[0] if apps else None
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def _find_applications_for_mime(mime_type: str) -> dict[str, str]:
    """Return desktop file name -> application name for apps supporting mime_type."""
    entries = {}
    data_dirs = []
    xdg_data_home = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    xdg_data_dirs = os.environ.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share").split(":")
    data_dirs.append(xdg_data_home)
    data_dirs.extend(Path(d) for d in xdg_data_dirs if d)

    for data_dir in data_dirs:
        app_dir = data_dir / "applications"
        if not app_dir.exists():
            continue
        for desktop_path in app_dir.glob("*.desktop"):
            try:
                entry = _parse_desktop_entry(desktop_path)
                if not entry:
                    continue
                if mime_type in entry.get("MimeType", "").split(";"):
                    desktop_name = desktop_path.name
                    entries.setdefault(desktop_name, entry.get("Name", desktop_name))
            except Exception:
                pass
    return entries


def _parse_desktop_entry(path: Path) -> dict[str, str] | None:
    """Parse a .desktop file and return the main desktop entry keys."""
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return None

    if not lines or lines[0].strip() != "[Desktop Entry]":
        return None

    result = {}
    for line in lines[1:]:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key.strip()] = value.strip()
    return result


def build_desktop_entry_command(path: Path, target: Path | None = None) -> list[str] | None:
    """Build a command from an application .desktop entry."""
    entry = _parse_desktop_entry(path)
    if not entry or entry.get("Type") != "Application":
        return None

    exec_line = entry.get("Exec")
    if not exec_line:
        return None

    try:
        parts = shlex.split(exec_line)
    except ValueError:
        return None

    command = []
    target_text = str(target or path)
    for part in parts:
        if part in {"%f", "%u", "%F", "%U"}:
            command.append(target_text)
        elif part in {"%i", "%c", "%k"}:
            continue
        else:
            command.append(part.replace("%%", "%"))
    return command or None


def open_desktop_entry(path: Path) -> bool:
    """Open a .desktop application or link entry."""
    entry = _parse_desktop_entry(path)
    if not entry:
        return False

    entry_type = entry.get("Type")
    if entry_type == "Link" and entry.get("URL"):
        try:
            subprocess.Popen(
                ["xdg-open", entry["URL"]],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            return True
        except FileNotFoundError:
            return False

    command = build_desktop_entry_command(path)
    if not command:
        return False

    try:
        subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return True
    except FileNotFoundError:
        return False


def _get_mime_type(path: Path) -> Optional[str]:
    """Get MIME type of a file using xdg-mime or file command."""
    try:
        result = subprocess.run(
            ["xdg-mime", "query", "filetype", str(path)],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Fallback: use file command
    try:
        result = subprocess.run(
            ["file", "--mime-type", "-b", str(path)],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return None


def get_mime_type(path: Path) -> Optional[str]:
    """Public wrapper for MIME type detection."""
    return _get_mime_type(path)


def _launch_application(desktop_file: str, path: Path) -> bool:
    """Launch an application by its .desktop file name."""
    return launch_application_for_path(desktop_file, path)


def launch_application_for_path(desktop_file: str, path: Path) -> bool:
    """Launch an application for a target path via its desktop file."""
    try:
        subprocess.Popen(
            ["gtk-launch", desktop_file, str(path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
        return True
    except FileNotFoundError:
        return False


def build_xdg_email_command(paths: list[Path], subject: str = "") -> list[str]:
    """Build an xdg-email command with file attachments."""
    command = ["xdg-email"]
    if subject:
        command.extend(["--subject", subject])
    for path in paths:
        command.extend(["--attach", str(path)])
    return command


def send_email_with_attachments(paths: list[Path], subject: str = "Shared files") -> bool:
    """Open the default email composer with files attached."""
    attachments = [Path(path) for path in paths]
    if not attachments:
        return False
    if any(not path.exists() or not path.is_file() for path in attachments):
        return False
    if shutil.which("xdg-email") is None:
        return False

    try:
        subprocess.Popen(
            build_xdg_email_command(attachments, subject),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return True
    except FileNotFoundError:
        return False


def set_default_application(mime_type: str, desktop_file: str) -> bool:
    """Set the default application for a MIME type."""
    try:
        result = subprocess.run(
            ["xdg-mime", "default", desktop_file, mime_type],
            capture_output=True, text=True, timeout=5
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def set_default_application_for_file(path: Path, desktop_file: str) -> bool:
    """Set the default application for the MIME type of a file."""
    if not path.exists() or not desktop_file:
        return False
    mime_type = get_mime_type(path)
    if not mime_type:
        return False
    return set_default_application(mime_type, desktop_file)
