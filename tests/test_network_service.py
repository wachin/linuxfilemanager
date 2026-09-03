import shutil
import tempfile
import unittest
from pathlib import Path

from lfmapp.services.network_service import (
    discover_gvfs_locations,
    discover_network_locations,
    discover_proc_mount_network_locations,
    gvfs_root_for_user,
)


class NetworkServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_gvfs_root_for_user(self):
        self.assertEqual(gvfs_root_for_user(1000), Path("/run/user/1000/gvfs"))

    def test_discover_gvfs_locations_returns_mounted_directories(self):
        gvfs_root = self.temp_dir / "gvfs"
        gvfs_root.mkdir()
        smb_share = gvfs_root / "smb-share:server=server,share=docs"
        sftp_share = gvfs_root / "sftp:host=example.com"
        smb_share.mkdir()
        sftp_share.mkdir()

        self.assertEqual(
            discover_gvfs_locations(gvfs_root),
            [sftp_share, smb_share],
        )

    def test_discover_proc_mount_network_locations(self):
        mounts = self.temp_dir / "mounts"
        mounts.write_text(
            "\n".join(
                [
                    "/dev/sda1 / ext4 rw 0 0",
                    "//server/docs /mnt/docs cifs rw 0 0",
                    "server:/export /mnt/nfs nfs4 rw 0 0",
                    "sshfs#host:/files /mnt/remote\\040files fuse.sshfs rw 0 0",
                ]
            ),
            encoding="utf-8",
        )

        self.assertEqual(
            discover_proc_mount_network_locations(mounts),
            [
                Path("/mnt/docs"),
                Path("/mnt/nfs"),
                Path("/mnt/remote files"),
            ],
        )

    def test_discover_network_locations_deduplicates(self):
        gvfs_root = self.temp_dir / "gvfs"
        gvfs_root.mkdir()
        gvfs_location = gvfs_root / "smb-share:server=server,share=docs"
        gvfs_location.mkdir()

        mounts = self.temp_dir / "mounts"
        mounts.write_text(
            f"//server/docs {gvfs_location} cifs rw 0 0\n",
            encoding="utf-8",
        )

        self.assertEqual(
            discover_network_locations(gvfs_root, mounts),
            [gvfs_location],
        )


if __name__ == "__main__":
    unittest.main()
