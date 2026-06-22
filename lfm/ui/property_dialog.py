import grp
import pwd
import stat
from datetime import datetime
from pathlib import Path

from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMessageBox,
)


class PropertyDialog(QDialog):
    def __init__(self, path: Path, parent=None):
        super().__init__(parent)
        self.path = Path(path)
        self._permission_checks: dict[tuple[str, str], QCheckBox] = {}
        self.setWindowTitle(self.tr("Properties"))
        self.resize(560, 380)

        layout = QFormLayout(self)
        try:
            st = self.path.stat()
            size = st.st_size if self.path.is_file() else self._folder_size(self.path)
            modified = datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            created = datetime.fromtimestamp(st.st_ctime).strftime("%Y-%m-%d %H:%M:%S")
            owner = self._owner_name(st.st_uid)
            group = self._group_name(st.st_gid)
            permissions = stat.filemode(st.st_mode)
        except OSError:
            st = None
            size = 0
            modified = self.tr("Unavailable")
            created = self.tr("Unavailable")
            owner = self.tr("Unavailable")
            group = self.tr("Unavailable")
            permissions = self.tr("Unavailable")

        layout.addRow(self.tr("Name:"), QLabel(self.path.name))
        layout.addRow(self.tr("Path:"), QLabel(str(self.path)))
        layout.addRow(self.tr("Type:"), QLabel(self.tr("Directory") if self.path.is_dir() else self.tr("File")))
        layout.addRow(self.tr("Size:"), QLabel(self.tr("{size} bytes").format(size=size)))
        layout.addRow(self.tr("Modified:"), QLabel(modified))
        layout.addRow(self.tr("Changed:"), QLabel(created))
        layout.addRow(self.tr("Owner:"), QLabel(owner))
        layout.addRow(self.tr("Group:"), QLabel(group))
        self.permissions_label = QLabel(permissions)
        layout.addRow(self.tr("Permissions:"), self.permissions_label)

        self.permissions_group = self._build_permissions_group(st.st_mode if st else 0)
        self.permissions_group.setEnabled(st is not None)
        layout.addRow(self.permissions_group)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.Apply
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        apply_button = button_box.button(QDialogButtonBox.StandardButton.Apply)
        if apply_button is not None:
            apply_button.clicked.connect(self.apply_permissions)
        layout.addRow(button_box)

    def accept(self):
        if self.apply_permissions():
            super().accept()

    def apply_permissions(self) -> bool:
        """Apply permission checkbox values to the file."""
        try:
            new_mode = self.apply_permission_state_to_path(
                self.path,
                self.permission_state_from_checks(),
            )
            self.permissions_label.setText(stat.filemode(new_mode))
            return True
        except OSError as exc:
            QMessageBox.critical(
                self,
                self.tr("Permission Error"),
                self.tr("Could not update permissions:\n{error}").format(error=exc),
            )
            return False

    def _build_permissions_group(self, mode: int) -> QGroupBox:
        group = QGroupBox(self.tr("Permissions"))
        grid = QGridLayout(group)
        grid.addWidget(QLabel(self.tr("Read")), 0, 1)
        grid.addWidget(QLabel(self.tr("Write")), 0, 2)
        grid.addWidget(QLabel(self.tr("Execute")), 0, 3)

        state = self.permission_state_from_mode(mode)
        rows = [(self.tr("User"), "user"), (self.tr("Group"), "group"), (self.tr("Others"), "others")]
        columns = [("read", 1), ("write", 2), ("execute", 3)]

        for row, (label, scope) in enumerate(rows, start=1):
            grid.addWidget(QLabel(label), row, 0)
            for permission, column in columns:
                checkbox = QCheckBox()
                checkbox.setChecked(state[(scope, permission)])
                grid.addWidget(checkbox, row, column)
                self._permission_checks[(scope, permission)] = checkbox

        return group

    def permission_state_from_checks(self) -> dict[tuple[str, str], bool]:
        return {
            key: checkbox.isChecked()
            for key, checkbox in self._permission_checks.items()
        }

    @staticmethod
    def _folder_size(root: Path) -> int:
        total = 0
        for item in root.rglob("*"):
            if item.is_file():
                try:
                    total += item.stat().st_size
                except OSError:
                    pass
        return total

    @staticmethod
    def _owner_name(uid: int) -> str:
        try:
            return f"{pwd.getpwuid(uid).pw_name} ({uid})"
        except KeyError:
            return str(uid)

    @staticmethod
    def _group_name(gid: int) -> str:
        try:
            return f"{grp.getgrgid(gid).gr_name} ({gid})"
        except KeyError:
            return str(gid)

    @staticmethod
    def permission_state_from_mode(mode: int) -> dict[tuple[str, str], bool]:
        mode = stat.S_IMODE(mode)
        masks = {
            ("user", "read"): stat.S_IRUSR,
            ("user", "write"): stat.S_IWUSR,
            ("user", "execute"): stat.S_IXUSR,
            ("group", "read"): stat.S_IRGRP,
            ("group", "write"): stat.S_IWGRP,
            ("group", "execute"): stat.S_IXGRP,
            ("others", "read"): stat.S_IROTH,
            ("others", "write"): stat.S_IWOTH,
            ("others", "execute"): stat.S_IXOTH,
        }
        return {key: bool(mode & mask) for key, mask in masks.items()}

    @staticmethod
    def mode_from_permission_state(state: dict[tuple[str, str], bool]) -> int:
        masks = {
            ("user", "read"): stat.S_IRUSR,
            ("user", "write"): stat.S_IWUSR,
            ("user", "execute"): stat.S_IXUSR,
            ("group", "read"): stat.S_IRGRP,
            ("group", "write"): stat.S_IWGRP,
            ("group", "execute"): stat.S_IXGRP,
            ("others", "read"): stat.S_IROTH,
            ("others", "write"): stat.S_IWOTH,
            ("others", "execute"): stat.S_IXOTH,
        }
        mode = 0
        for key, enabled in state.items():
            if enabled:
                mode |= masks[key]
        return mode

    @staticmethod
    def apply_permission_state_to_path(path: Path, state: dict[tuple[str, str], bool]) -> int:
        """Apply permission checkbox state to a path and return the resulting mode."""
        current_mode = path.stat().st_mode
        permission_mode = PropertyDialog.mode_from_permission_state(state)
        new_mode = (current_mode & ~0o777) | permission_mode
        if stat.S_IMODE(current_mode) != permission_mode:
            path.chmod(new_mode)
        return new_mode


class AdvancedSecurityDialog(QDialog):
    """POSIX permission editor for advanced security settings."""

    SPECIAL_KEYS = ("setuid", "setgid", "sticky")

    def __init__(self, path: Path, parent=None):
        super().__init__(parent)
        self.path = Path(path)
        self._permission_checks: dict[tuple[str, str], QCheckBox] = {}
        self._special_checks: dict[str, QCheckBox] = {}
        self.setWindowTitle(self.tr("Advanced Security"))
        self.resize(560, 420)

        layout = QFormLayout(self)
        try:
            st = self.path.stat()
            owner = PropertyDialog._owner_name(st.st_uid)
            group = PropertyDialog._group_name(st.st_gid)
            mode = stat.S_IMODE(st.st_mode)
            permissions = stat.filemode(st.st_mode)
        except OSError:
            st = None
            owner = self.tr("Unavailable")
            group = self.tr("Unavailable")
            mode = 0
            permissions = self.tr("Unavailable")

        layout.addRow(self.tr("Name:"), QLabel(self.path.name))
        layout.addRow(self.tr("Path:"), QLabel(str(self.path)))
        layout.addRow(self.tr("Owner:"), QLabel(owner))
        layout.addRow(self.tr("Group:"), QLabel(group))
        self.permissions_label = QLabel(permissions)
        layout.addRow(self.tr("Current permissions:"), self.permissions_label)

        self.octal_edit = QLineEdit(self.format_mode(mode))
        self.octal_edit.setMaxLength(4)
        self.octal_edit.textEdited.connect(self.on_octal_edited)
        layout.addRow(self.tr("Octal mode:"), self.octal_edit)

        self.permissions_group = self._build_permissions_group(mode)
        self.permissions_group.setEnabled(st is not None)
        layout.addRow(self.permissions_group)

        self.special_group = self._build_special_group(mode)
        self.special_group.setEnabled(st is not None)
        layout.addRow(self.special_group)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.Apply
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        apply_button = button_box.button(QDialogButtonBox.StandardButton.Apply)
        if apply_button is not None:
            apply_button.clicked.connect(self.apply_security)
        layout.addRow(button_box)

    def accept(self):
        if self.apply_security():
            super().accept()

    def _build_permissions_group(self, mode: int) -> QGroupBox:
        group = QGroupBox(self.tr("Access permissions"))
        grid = QGridLayout(group)
        grid.addWidget(QLabel(self.tr("Read")), 0, 1)
        grid.addWidget(QLabel(self.tr("Write")), 0, 2)
        grid.addWidget(QLabel(self.tr("Execute")), 0, 3)

        state = PropertyDialog.permission_state_from_mode(mode)
        rows = [(self.tr("User"), "user"), (self.tr("Group"), "group"), (self.tr("Others"), "others")]
        columns = [("read", 1), ("write", 2), ("execute", 3)]

        for row, (label, scope) in enumerate(rows, start=1):
            grid.addWidget(QLabel(label), row, 0)
            for permission, column in columns:
                checkbox = QCheckBox()
                checkbox.setChecked(state[(scope, permission)])
                checkbox.stateChanged.connect(self.update_octal_from_checks)
                grid.addWidget(checkbox, row, column)
                self._permission_checks[(scope, permission)] = checkbox

        return group

    def _build_special_group(self, mode: int) -> QGroupBox:
        group = QGroupBox(self.tr("Special permissions"))
        grid = QGridLayout(group)
        labels = {
            "setuid": self.tr("Set user ID"),
            "setgid": self.tr("Set group ID"),
            "sticky": self.tr("Sticky bit"),
        }
        state = self.special_state_from_mode(mode)
        for row, key in enumerate(self.SPECIAL_KEYS):
            checkbox = QCheckBox(labels[key])
            checkbox.setChecked(state[key])
            checkbox.stateChanged.connect(self.update_octal_from_checks)
            grid.addWidget(checkbox, row, 0)
            self._special_checks[key] = checkbox
        return group

    def permission_state_from_checks(self) -> dict[tuple[str, str], bool]:
        return {
            key: checkbox.isChecked()
            for key, checkbox in self._permission_checks.items()
        }

    def special_state_from_checks(self) -> dict[str, bool]:
        return {
            key: checkbox.isChecked()
            for key, checkbox in self._special_checks.items()
        }

    def update_octal_from_checks(self):
        mode = self.mode_from_security_state(
            self.permission_state_from_checks(),
            self.special_state_from_checks(),
        )
        self.octal_edit.setText(self.format_mode(mode))

    def on_octal_edited(self, text: str):
        try:
            mode = self.parse_octal_mode(text)
        except ValueError:
            return
        self.set_checks_from_mode(mode)

    def set_checks_from_mode(self, mode: int):
        permission_state = PropertyDialog.permission_state_from_mode(mode)
        special_state = self.special_state_from_mode(mode)
        for key, checkbox in self._permission_checks.items():
            checkbox.blockSignals(True)
            checkbox.setChecked(permission_state[key])
            checkbox.blockSignals(False)
        for key, checkbox in self._special_checks.items():
            checkbox.blockSignals(True)
            checkbox.setChecked(special_state[key])
            checkbox.blockSignals(False)

    def apply_security(self) -> bool:
        try:
            mode = self.parse_octal_mode(self.octal_edit.text())
            new_mode = self.apply_mode_to_path(self.path, mode)
            self.permissions_label.setText(stat.filemode(new_mode))
            self.set_checks_from_mode(new_mode)
            self.octal_edit.setText(self.format_mode(new_mode))
            return True
        except ValueError:
            error = self.tr("Enter a 3 or 4 digit octal mode, for example 755 or 1755.")
            QMessageBox.critical(
                self,
                self.tr("Advanced Security Error"),
                self.tr("Could not update permissions:\n{error}").format(error=error),
            )
            return False
        except OSError as exc:
            QMessageBox.critical(
                self,
                self.tr("Advanced Security Error"),
                self.tr("Could not update permissions:\n{error}").format(error=exc),
            )
            return False

    @staticmethod
    def special_state_from_mode(mode: int) -> dict[str, bool]:
        mode = stat.S_IMODE(mode)
        return {
            "setuid": bool(mode & stat.S_ISUID),
            "setgid": bool(mode & stat.S_ISGID),
            "sticky": bool(mode & stat.S_ISVTX),
        }

    @staticmethod
    def mode_from_security_state(
        permissions: dict[tuple[str, str], bool],
        special: dict[str, bool],
    ) -> int:
        mode = PropertyDialog.mode_from_permission_state(permissions)
        if special.get("setuid"):
            mode |= stat.S_ISUID
        if special.get("setgid"):
            mode |= stat.S_ISGID
        if special.get("sticky"):
            mode |= stat.S_ISVTX
        return mode

    @staticmethod
    def parse_octal_mode(value: str) -> int:
        value = value.strip()
        if len(value) not in (3, 4) or any(char not in "01234567" for char in value):
            raise ValueError("Enter a 3 or 4 digit octal mode, for example 755 or 1755.")
        return int(value, 8)

    @staticmethod
    def format_mode(mode: int) -> str:
        return f"{stat.S_IMODE(mode):04o}"

    @staticmethod
    def apply_mode_to_path(path: Path, mode: int) -> int:
        current_mode = path.stat().st_mode
        permission_mode = stat.S_IMODE(mode)
        new_mode = (current_mode & ~0o7777) | permission_mode
        if stat.S_IMODE(current_mode) != permission_mode:
            path.chmod(new_mode)
        return new_mode
