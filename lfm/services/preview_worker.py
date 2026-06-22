"""Preview worker thread for linux-file-manager.

Loads preview content in a background thread to avoid UI freezing.
"""

from datetime import datetime
import grp
import mimetypes
from pathlib import Path
import pwd
import shutil
import stat
import subprocess
import tempfile
import wave
import zipfile
import xml.etree.ElementTree as ET

from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtGui import QPixmap, QImage


class PreviewWorker(QThread):
    """Load preview content in a background thread."""

    image_ready = pyqtSignal(QPixmap)
    text_ready = pyqtSignal(str)
    metadata_ready = pyqtSignal(str)

    def __init__(self, path: Path, parent=None):
        super().__init__(parent)
        self.path = path
        self._running = True

    def run(self):
        if not self.path or not self.path.exists():
            return

        self._load_metadata()

        if self.path.is_dir():
            return

        if self._is_image(self.path):
            self._load_image()
        elif self._is_video(self.path):
            self._load_video_frame()
        elif self._is_document(self.path):
            self._load_document()
        elif self._is_text(self.path):
            self._load_text()

    def _load_image(self):
        """Load and scale an image in the background."""
        try:
            pixmap = QPixmap(str(self.path))
            if not pixmap.isNull() and self._running:
                scaled = pixmap.scaled(320, 240, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                self.image_ready.emit(scaled)
        except Exception:
            pass

    def _load_text(self):
        """Read text file content in the background."""
        try:
            content = self.path.read_text(encoding="utf-8", errors="replace")
            if self._running:
                self.text_ready.emit(content[:20000])
        except Exception:
            pass

    def _load_video_frame(self):
        """Extract a lightweight video thumbnail when ffmpeg is available."""
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            return

        try:
            with tempfile.NamedTemporaryFile(suffix=".jpg") as frame:
                result = subprocess.run(
                    [
                        ffmpeg,
                        "-hide_banner",
                        "-loglevel",
                        "error",
                        "-y",
                        "-ss",
                        "00:00:01",
                        "-i",
                        str(self.path),
                        "-frames:v",
                        "1",
                        "-vf",
                        "scale='min(320,iw)':-1",
                        frame.name,
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=5,
                    check=False,
                )
                if result.returncode != 0 or not self._running:
                    return

                pixmap = QPixmap(frame.name)
                if not pixmap.isNull() and self._running:
                    self.image_ready.emit(pixmap)
        except (OSError, subprocess.SubprocessError):
            pass

    def _load_document(self):
        """Load a lightweight first-page document preview."""
        try:
            content = self.document_preview_for_path(self.path)
            if content and self._running:
                self.text_ready.emit(content[:20000])
        except Exception:
            pass

    def _load_metadata(self):
        """Generate metadata string for a file."""
        try:
            metadata = self.metadata_for_path(self.path)
            if self._running:
                self.metadata_ready.emit(metadata)
        except OSError:
            pass

    def stop(self):
        self._running = False

    @staticmethod
    def _is_image(path: Path) -> bool:
        return path.suffix.lower() in {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".svg", ".webp"}

    @staticmethod
    def _is_text(path: Path) -> bool:
        return path.suffix.lower() in {
            ".txt", ".md", ".py", ".json", ".log", ".ini", ".cfg",
            ".csv", ".sh", ".yaml", ".yml", ".xml", ".toml",
        }

    @staticmethod
    def _is_audio(path: Path) -> bool:
        return path.suffix.lower() in {".mp3", ".wav", ".ogg", ".flac", ".aac", ".m4a", ".opus"}

    @staticmethod
    def _is_video(path: Path) -> bool:
        return path.suffix.lower() in {
            ".mp4", ".m4v", ".mkv", ".avi", ".mov", ".webm", ".wmv", ".flv", ".mpeg", ".mpg",
        }

    @staticmethod
    def _is_document(path: Path) -> bool:
        return path.suffix.lower() in {".pdf", ".docx", ".odt", ".rtf"}

    @staticmethod
    def _human_size(size: int) -> str:
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024:
                if unit == "B":
                    return f"{size} {unit}"
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} PB"

    @staticmethod
    def metadata_for_path(path: Path) -> str:
        """Return display metadata for a path."""
        st = path.stat()
        mode = st.st_mode
        mime_type, _ = mimetypes.guess_type(path.name)
        if path.is_dir():
            file_type = "Folder"
        elif mime_type:
            file_type = mime_type
        elif path.suffix:
            file_type = f"{path.suffix.lstrip('.').upper()} file"
        else:
            file_type = "File"

        try:
            owner = pwd.getpwuid(st.st_uid).pw_name
        except KeyError:
            owner = str(st.st_uid)

        try:
            group = grp.getgrgid(st.st_gid).gr_name
        except KeyError:
            group = str(st.st_gid)

        lines = [
            f"Name: {path.name}",
            f"Path: {path}",
            f"Type: {file_type}",
            f"Size: {PreviewWorker._human_size(st.st_size)}",
            f"Modified: {PreviewWorker._format_time(st.st_mtime)}",
            f"Accessed: {PreviewWorker._format_time(st.st_atime)}",
            f"Owner: {owner}",
            f"Group: {group}",
            f"Permissions: {stat.filemode(mode)} ({stat.S_IMODE(mode):04o})",
        ]

        birth_time = getattr(st, "st_birthtime", None)
        if birth_time is not None:
            lines.insert(6, f"Created: {PreviewWorker._format_time(birth_time)}")
        else:
            lines.insert(6, f"Changed: {PreviewWorker._format_time(st.st_ctime)}")

        if PreviewWorker._is_audio(path):
            lines.extend(PreviewWorker.audio_metadata_for_path(path))
        elif PreviewWorker._is_video(path):
            lines.extend(PreviewWorker.video_metadata_for_path(path))

        return "\n".join(lines)

    @staticmethod
    def _format_time(timestamp: float) -> str:
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def audio_metadata_for_path(path: Path) -> list[str]:
        """Return audio-specific metadata lines when available."""
        lines = ["Audio: Yes"]
        if path.suffix.lower() == ".wav":
            try:
                with wave.open(str(path), "rb") as wav:
                    frame_count = wav.getnframes()
                    frame_rate = wav.getframerate()
                    duration = frame_count / frame_rate if frame_rate else 0
                    lines.extend(
                        [
                            f"Duration: {PreviewWorker._format_duration(duration)}",
                            f"Channels: {wav.getnchannels()}",
                            f"Sample rate: {frame_rate} Hz",
                            f"Sample width: {wav.getsampwidth() * 8} bit",
                        ]
                    )
            except (wave.Error, OSError):
                lines.append("Audio metadata: Unavailable")
        return lines

    @staticmethod
    def video_metadata_for_path(path: Path) -> list[str]:
        """Return video-specific metadata lines when available."""
        lines = ["Video: Yes"]
        ffprobe = shutil.which("ffprobe")
        if not ffprobe:
            lines.append("Video metadata: Install ffmpeg for duration and frame details")
            return lines

        try:
            result = subprocess.run(
                [
                    ffprobe,
                    "-v",
                    "error",
                    "-select_streams",
                    "v:0",
                    "-show_entries",
                    "stream=width,height,codec_name,r_frame_rate:format=duration",
                    "-of",
                    "default=noprint_wrappers=1:nokey=0",
                    str(path),
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            lines.append("Video metadata: Unavailable")
            return lines

        if result.returncode != 0:
            lines.append("Video metadata: Unavailable")
            return lines

        values = PreviewWorker._parse_ffprobe_output(result.stdout)
        if values.get("duration"):
            try:
                lines.append(f"Duration: {PreviewWorker._format_duration(float(values['duration']))}")
            except ValueError:
                pass
        if values.get("width") and values.get("height"):
            lines.append(f"Dimensions: {values['width']}x{values['height']}")
        if values.get("codec_name"):
            lines.append(f"Video codec: {values['codec_name']}")
        if values.get("r_frame_rate"):
            fps = PreviewWorker._format_frame_rate(values["r_frame_rate"])
            if fps:
                lines.append(f"Frame rate: {fps}")

        if len(lines) == 1:
            lines.append("Video metadata: Unavailable")
        return lines

    @staticmethod
    def _parse_ffprobe_output(output: str) -> dict[str, str]:
        values = {}
        for line in output.splitlines():
            key, separator, value = line.partition("=")
            if separator and value:
                values[key] = value
        return values

    @staticmethod
    def _format_frame_rate(value: str) -> str:
        numerator, separator, denominator = value.partition("/")
        try:
            if separator:
                rate = float(numerator) / float(denominator)
            else:
                rate = float(value)
        except (ValueError, ZeroDivisionError):
            return ""

        if rate.is_integer():
            return f"{int(rate)} fps"
        return f"{rate:.2f} fps"

    @staticmethod
    def document_preview_for_path(path: Path) -> str:
        """Return a lightweight preview for supported document formats."""
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            return PreviewWorker._pdf_preview_for_path(path)
        if suffix == ".docx":
            return PreviewWorker._docx_preview_for_path(path)
        if suffix == ".odt":
            return PreviewWorker._odt_preview_for_path(path)
        if suffix == ".rtf":
            return PreviewWorker._rtf_preview_for_path(path)
        return ""

    @staticmethod
    def _pdf_preview_for_path(path: Path) -> str:
        pdftotext = shutil.which("pdftotext")
        if not pdftotext:
            return "Document preview: Install poppler-utils to preview PDF pages."

        try:
            result = subprocess.run(
                [
                    pdftotext,
                    "-f",
                    "1",
                    "-l",
                    "3",
                    "-layout",
                    "-enc",
                    "UTF-8",
                    str(path),
                    "-",
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return "Document preview: Unavailable"

        if result.returncode != 0:
            return "Document preview: Unavailable"
        return result.stdout.strip() or "Document preview: No extractable text found."

    @staticmethod
    def _docx_preview_for_path(path: Path) -> str:
        try:
            with zipfile.ZipFile(path) as archive:
                xml_data = archive.read("word/document.xml")
        except (KeyError, OSError, zipfile.BadZipFile):
            return "Document preview: Unavailable"

        return (
            PreviewWorker._text_from_xml(xml_data, text_suffix="}t")
            or "Document preview: No extractable text found."
        )

    @staticmethod
    def _odt_preview_for_path(path: Path) -> str:
        try:
            with zipfile.ZipFile(path) as archive:
                xml_data = archive.read("content.xml")
        except (KeyError, OSError, zipfile.BadZipFile):
            return "Document preview: Unavailable"

        return (
            PreviewWorker._text_from_xml(xml_data, text_suffix="}p")
            or "Document preview: No extractable text found."
        )

    @staticmethod
    def _text_from_xml(xml_data: bytes, text_suffix: str) -> str:
        try:
            root = ET.fromstring(xml_data)
        except ET.ParseError:
            return ""

        parts = []
        for element in root.iter():
            if element.tag.endswith(text_suffix) and element.text:
                text = element.text.strip()
                if text:
                    parts.append(text)
        return "\n".join(parts)

    @staticmethod
    def _rtf_preview_for_path(path: Path) -> str:
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return "Document preview: Unavailable"

        text = []
        index = 0
        while index < len(content):
            char = content[index]
            if char in "{}":
                index += 1
            elif char == "\\":
                index += 1
                if index < len(content) and content[index] in "\\{}":
                    text.append(content[index])
                    index += 1
                    continue
                while index < len(content) and content[index].isalpha():
                    index += 1
                while index < len(content) and content[index].isdigit():
                    index += 1
                if index < len(content) and content[index] == " ":
                    index += 1
            else:
                text.append(char)
                index += 1

        preview = "".join(text).strip()
        return preview or "Document preview: No extractable text found."

    @staticmethod
    def _format_duration(seconds: float) -> str:
        total_seconds = int(round(seconds))
        minutes, seconds = divmod(total_seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours:d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:d}:{seconds:02d}"
