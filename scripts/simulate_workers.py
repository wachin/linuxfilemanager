#!/usr/bin/env python3
"""Simulate multiple worker operations to exercise progress UI.

Run with: python3 scripts/simulate_workers.py

This script creates temporary files and starts several `CopyWorker` threads
from the application to exercise progress reporting without launching the GUI.
"""
import os
import sys
import tempfile
from pathlib import Path
from PyQt6.QtCore import QCoreApplication, QTimer

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from lfmapp.services.worker_threads import CopyWorker


def main():
    app = QCoreApplication(sys.argv)
    tmp = Path(tempfile.mkdtemp(prefix="lfm-sim-"))
    src = tmp / "src"
    dst = tmp / "dst"
    src.mkdir(parents=True)
    dst.mkdir(parents=True)

    files = []
    for i in range(3):
        f = src / f"file_{i}.dat"
        with f.open("wb") as fh:
            fh.write(b"x" * 1024 * 512)  # 512 KB
        files.append(f)

    workers = []
    finished = []

    def on_finished(success, msg):
        finished.append((success, msg))
        print("Finished:", success, msg)
        # quit when all workers finished
        if len(finished) >= len(files):
            QTimer.singleShot(100, app.quit)

    for f in files:
        w = CopyWorker(f, dst)
        # capture current file name in callback
        w.progress.connect(lambda v, fname=f.name: print(f"Progress {fname}: {v}%"))
        w.finished.connect(on_finished)
        w.start()
        workers.append(w)

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
