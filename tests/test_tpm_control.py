import tempfile
import unittest
from pathlib import Path

from lfmapp.services import TpmControlService, TpmControlStatus


class TpmControlServiceTests(unittest.TestCase):
    def test_status_reports_unavailable_without_device_node(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            missing_device = Path(tmpdir) / "missing-tpm"
            service = TpmControlService([missing_device])

            status = service.status()

        self.assertIsInstance(status, TpmControlStatus)
        self.assertFalse(status.available)
        self.assertIsNone(status.device_path)
        self.assertIn("No TPM", status.message)

    def test_status_reports_available_device_node(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            device = Path(tmpdir) / "tpmrm0"
            device.touch()
            service = TpmControlService([device])

            status = service.status()

        self.assertTrue(status.available)
        self.assertEqual(status.device_path, device)

    def test_secret_sealing_is_explicitly_not_implemented(self):
        service = TpmControlService([])

        with self.assertRaises(NotImplementedError):
            service.seal_secret(b"secret")
        with self.assertRaises(NotImplementedError):
            service.unseal_secret(b"sealed")


if __name__ == "__main__":
    unittest.main()
