import tempfile
import unittest
import wave
import zipfile
from pathlib import Path
from unittest.mock import patch

from lfm.services.preview_worker import PreviewWorker


class PreviewWorkerMetadataTests(unittest.TestCase):
    def test_metadata_for_file_includes_details(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "notes.txt"
            path.write_text("hello", encoding="utf-8")

            metadata = PreviewWorker.metadata_for_path(path)

        self.assertIn("Name: notes.txt", metadata)
        self.assertIn(f"Path: {path}", metadata)
        self.assertIn("Type: text/plain", metadata)
        self.assertIn("Size: 5 B", metadata)
        self.assertIn("Modified:", metadata)
        self.assertIn("Accessed:", metadata)
        self.assertTrue("Created:" in metadata or "Changed:" in metadata)
        self.assertIn("Owner:", metadata)
        self.assertIn("Group:", metadata)
        self.assertIn("Permissions:", metadata)

    def test_metadata_for_directory_identifies_folder(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir)

            metadata = PreviewWorker.metadata_for_path(path)

        self.assertIn("Type: Folder", metadata)
        self.assertIn("Permissions:", metadata)

    def test_metadata_for_wav_includes_audio_details(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "tone.wav"
            with wave.open(str(path), "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(8000)
                wav.writeframes(b"\x00\x00" * 8000)

            metadata = PreviewWorker.metadata_for_path(path)

        self.assertIn("Type: audio/x-wav", metadata)
        self.assertIn("Audio: Yes", metadata)
        self.assertIn("Duration: 0:01", metadata)
        self.assertIn("Channels: 1", metadata)
        self.assertIn("Sample rate: 8000 Hz", metadata)
        self.assertIn("Sample width: 16 bit", metadata)

    def test_metadata_for_video_without_ffprobe_includes_video_notice(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "clip.mp4"
            path.write_bytes(b"not a real video")

            with patch("lfm.services.preview_worker.shutil.which", return_value=None):
                metadata = PreviewWorker.metadata_for_path(path)

        self.assertIn("Video: Yes", metadata)
        self.assertIn("Video metadata: Install ffmpeg for duration and frame details", metadata)

    def test_ffprobe_output_helpers(self):
        values = PreviewWorker._parse_ffprobe_output(
            "width=1920\nheight=1080\ncodec_name=h264\nr_frame_rate=30000/1001\nduration=2.4\n"
        )

        self.assertEqual(values["width"], "1920")
        self.assertEqual(values["height"], "1080")
        self.assertEqual(values["codec_name"], "h264")
        self.assertEqual(PreviewWorker._format_frame_rate(values["r_frame_rate"]), "29.97 fps")
        self.assertEqual(PreviewWorker._format_frame_rate("30/1"), "30 fps")

    def test_docx_preview_extracts_document_text(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "document.docx"
            document_xml = (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                "<w:body><w:p><w:r><w:t>First page text</w:t></w:r></w:p></w:body>"
                "</w:document>"
            )
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("word/document.xml", document_xml)

            preview = PreviewWorker.document_preview_for_path(path)

        self.assertEqual(preview, "First page text")

    def test_pdf_preview_without_pdftotext_includes_install_notice(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "document.pdf"
            path.write_bytes(b"%PDF-1.4")

            with patch("lfm.services.preview_worker.shutil.which", return_value=None):
                preview = PreviewWorker.document_preview_for_path(path)

        self.assertIn("Install poppler-utils", preview)

    def test_duration_format(self):
        self.assertEqual(PreviewWorker._format_duration(1), "0:01")
        self.assertEqual(PreviewWorker._format_duration(65), "1:05")
        self.assertEqual(PreviewWorker._format_duration(3661), "1:01:01")


if __name__ == "__main__":
    unittest.main()
