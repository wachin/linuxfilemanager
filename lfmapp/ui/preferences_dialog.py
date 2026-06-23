from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFileDialog,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFontComboBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from lfmapp.extensions.manager import ExtensionManager
from lfmapp.ui.icons import app_icon


class PreferencesDialog(QDialog):
    STYLE_OPTIONS = [
        ("Normal", 400, False),
        ("Bold", 700, False),
        ("Italic", 400, True),
        ("Bold Italic", 700, True),
    ]
    STARTUP_LOCATION_OPTIONS = [
        ("Home folder", "home"),
        ("Last visited folder", "last_visited"),
        ("Custom folder", "custom"),
    ]
    VIEW_MODE_OPTIONS = [
        ("Icon View", "icon"),
        ("List View", "list"),
        ("Details View", "details"),
        ("Compact View", "compact"),
    ]
    SORT_OPTIONS = [
        ("By Name", "name"),
        ("By Size", "size"),
        ("By Type", "type"),
        ("By Date Modified", "modified"),
    ]
    ZOOM_OPTIONS = [50, 67, 75, 100, 150, 200]
    EXECUTABLE_TEXT_OPTIONS = [
        ("Run executable text files when they are opened", "run"),
        ("View executable text files when they are opened", "view"),
        ("Ask each time", "ask"),
    ]
    THUMBNAIL_OPTIONS = [
        ("Never", "never"),
        ("Local Files Only", "local_only"),
        ("Always", "always"),
    ]
    FILE_SIZE_PREFIX_OPTIONS = [
        ("Decimal", "decimal"),
        ("Binary", "binary"),
    ]
    ICON_CAPTION_FIELDS = [
        ("None", "none"),
        ("Size", "size"),
        ("Date Modified", "date_modified"),
        ("Type", "type"),
    ]
    LIST_COLUMN_LABELS = [
        ("name", "Name"),
        ("size", "Size"),
        ("type", "Type"),
        ("modified", "Date Modified"),
        ("created_time", "Created - Time"),
        ("accessed_time", "Date Accessed"),
        ("created_date", "Date Created"),
        ("detailed_type", "Detailed Type"),
        ("group", "Group"),
        ("location", "Location"),
        ("mime_type", "MIME Type"),
        ("modified_time", "Modified - Time"),
        ("octal_permissions", "Octal Permissions"),
        ("owner", "Owner"),
        ("permissions", "Permissions"),
        ("selinux_context", "SELinux Context"),
    ]
    TOOLBAR_BUTTON_LABELS = [
        ("back", "Previous"),
        ("up", "Up"),
        ("computer", "Computer"),
        ("location_toggle", "Location entry toggle"),
        ("new_folder", "New folder"),
        ("icon_view", "Icon view"),
        ("compact_view", "Compact view"),
        ("next", "Next"),
        ("refresh", "Refresh"),
        ("home", "Home"),
        ("open_terminal", "Open in terminal"),
        ("search", "Search"),
        ("list_view", "List view"),
        ("show_thumbnails", "Show Thumbnails"),
    ]
    CONTEXT_GROUPS = {
        "selection": [
            ("open", "Open"),
            ("open_in_new_tab", "Open in New Tab"),
            ("open_in_new_window", "Open in New Window"),
            ("scripts", "Scripts"),
            ("cut", "Cut"),
            ("copy", "Copy"),
            ("paste", "Paste"),
            ("duplicate", "Duplicate"),
            ("pin", "Pin"),
            ("favorite", "Favorite"),
            ("make_link", "Make Link"),
            ("rename", "Rename..."),
            ("copy_to", "Copy to"),
            ("move_to", "Move to"),
            ("open_in_terminal", "Open in Terminal"),
            ("open_as_root", "Open as Root"),
            ("move_to_trash", "Move to Trash"),
            ("properties", "Properties"),
        ],
        "background": [
            ("create_new_folder", "Create New Folder"),
            ("scripts", "Scripts"),
            ("open_in_terminal", "Open in Terminal"),
            ("open_as_root", "Open as Root"),
            ("show_hidden_files", "Show Hidden Files"),
            ("paste", "Paste"),
            ("properties", "Properties"),
        ],
        "icon_view": [
            ("arrange_items", "Arrange Items"),
            ("organize_by_name", "Organize by Name"),
        ],
        "desktop": [
            ("customize", "Customize"),
        ],
    }

    def __init__(self, config, terminal_service, parent=None):
        super().__init__(parent)
        self.config = config
        self.terminal_service = terminal_service
        self._extension_manager = ExtensionManager(
            enabled_extensions=self.config.enabled_extensions,
            extensions_enabled=self.config.extensions_enabled,
        )
        self._extensions = self._extension_manager.discover()
        self.setWindowTitle(self.tr("File Management Preferences"))
        self.resize(860, 740)

        root_layout = QVBoxLayout(self)
        body = QHBoxLayout()
        root_layout.addLayout(body, 1)

        self.nav_list = QListWidget(self)
        self.nav_list.setFixedWidth(130)
        self.nav_list.setSpacing(2)
        body.addWidget(self.nav_list)

        self.pages = QStackedWidget(self)
        body.addWidget(self.pages, 1)

        self._build_navigation()
        self._build_pages()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root_layout.addWidget(buttons)

        self._load_from_config()
        self.nav_list.setCurrentRow(0)
        self._update_font_preview()
        self._update_startup_location_controls()

    def _build_navigation(self):
        entries = [
            ("Views", "view-list-icons"),
            ("Behavior", "preferences-system"),
            ("Display", "view-visible"),
            ("List Columns", "view-list-details"),
            ("Preview", "view-preview"),
            ("Toolbar", "open-menu-symbolic"),
            ("Context Menus", "open-menu-symbolic"),
            ("Plugins", "applications-system"),
        ]
        for label, icon_name in entries:
            item = QListWidgetItem(app_icon(icon_name), self.tr(label))
            self.nav_list.addItem(item)
        self.nav_list.currentRowChanged.connect(self.pages.setCurrentIndex)

    def _add_page(self, title: str) -> QVBoxLayout:
        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(14)

        title_label = QLabel(self.tr(title), container)
        title_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(title_label)

        layout.addStretch(1)

        scroll_content = QWidget(self)
        scroll_content.setLayout(layout)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(scroll_content)
        self.pages.addWidget(scroll)
        return layout

    def _build_pages(self):
        self._build_views_page()
        self._build_behavior_page()
        self._build_display_page()
        self._build_list_columns_page()
        self._build_preview_page()
        self._build_toolbar_page()
        self._build_context_menus_page()
        self._build_plugins_page()

    def _build_views_page(self):
        layout = self._add_page("Default View")

        default_group = QGroupBox(self.tr("Default View"), self)
        default_form = QFormLayout(default_group)
        self.default_view_combo = QComboBox(self)
        for label, value in self.VIEW_MODE_OPTIONS:
            self.default_view_combo.addItem(self.tr(label), value)
        self.arrange_items_combo = QComboBox(self)
        for label, value in self.SORT_OPTIONS:
            self.arrange_items_combo.addItem(self.tr(label), value)
        self.inherit_view_checkbox = QCheckBox(self.tr("Inherit view type from parent"))
        self.reverse_sort_checkbox = QCheckBox(self.tr("Reverse sort"))
        self.sort_folders_first_checkbox = QCheckBox(self.tr("Sort folders before files"))
        self.sort_favorites_first_checkbox = QCheckBox(self.tr("Sort favorites before other files"))
        default_form.addRow(self.tr("View new folders using:"), self.default_view_combo)
        default_form.addRow("", self.inherit_view_checkbox)
        default_form.addRow(self.tr("Arrange items:"), self.arrange_items_combo)
        default_form.addRow("", self.reverse_sort_checkbox)
        default_form.addRow("", self.sort_folders_first_checkbox)
        default_form.addRow("", self.sort_favorites_first_checkbox)
        layout.insertWidget(layout.count() - 1, default_group)

        icon_group = QGroupBox(self.tr("Icon View Defaults"), self)
        icon_form = QFormLayout(icon_group)
        self.icon_zoom_combo = self._zoom_combo()
        self.icon_text_beside_checkbox = QCheckBox(self.tr("Text beside icons"))
        icon_form.addRow(self.tr("Default zoom level:"), self.icon_zoom_combo)
        icon_form.addRow("", self.icon_text_beside_checkbox)
        layout.insertWidget(layout.count() - 1, icon_group)

        compact_group = QGroupBox(self.tr("Compact View Defaults"), self)
        compact_form = QFormLayout(compact_group)
        self.compact_zoom_combo = self._zoom_combo()
        self.compact_equal_width_checkbox = QCheckBox(self.tr("All columns have the same width"))
        compact_form.addRow(self.tr("Default zoom level:"), self.compact_zoom_combo)
        compact_form.addRow("", self.compact_equal_width_checkbox)
        layout.insertWidget(layout.count() - 1, compact_group)

        list_group = QGroupBox(self.tr("List View Defaults"), self)
        list_form = QFormLayout(list_group)
        self.list_zoom_combo = self._zoom_combo()
        list_form.addRow(self.tr("Default zoom level:"), self.list_zoom_combo)
        layout.insertWidget(layout.count() - 1, list_group)

        tree_group = QGroupBox(self.tr("Tree View Defaults"), self)
        tree_form = QFormLayout(tree_group)
        self.tree_show_only_folders_checkbox = QCheckBox(self.tr("Show only folders"))
        tree_form.addRow("", self.tree_show_only_folders_checkbox)
        layout.insertWidget(layout.count() - 1, tree_group)

    def _build_behavior_page(self):
        layout = self._add_page("Behavior")

        behavior_group = QGroupBox(self.tr("Behavior"), self)
        behavior_box = QVBoxLayout(behavior_group)
        self.single_click_checkbox = QCheckBox(self.tr("Single click to open items"))
        self.double_click_checkbox = QCheckBox(self.tr("Double click to open items"))
        self.rename_second_click_checkbox = QCheckBox(self.tr("Click on a file's name twice to rename it"))
        self.open_folder_new_window_checkbox = QCheckBox(self.tr("Open each folder in its own window"))
        self.always_dual_pane_checkbox = QCheckBox(self.tr("Always start in dual-pane view"))
        self.ignore_folder_preferences_checkbox = QCheckBox(self.tr("Ignore per-folder view preferences"))
        self.disable_operation_queue_checkbox = QCheckBox(self.tr("Disable file operation queueing"))
        self.blank_area_go_up_checkbox = QCheckBox(self.tr("Double-click on a blank area to go to the parent folder"))
        for widget in (
            self.single_click_checkbox,
            self.double_click_checkbox,
            self.rename_second_click_checkbox,
            self.open_folder_new_window_checkbox,
            self.always_dual_pane_checkbox,
            self.ignore_folder_preferences_checkbox,
            self.disable_operation_queue_checkbox,
            self.blank_area_go_up_checkbox,
        ):
            behavior_box.addWidget(widget)
        self.single_click_checkbox.toggled.connect(
            lambda checked: checked and self.double_click_checkbox.setChecked(False)
        )
        self.double_click_checkbox.toggled.connect(
            lambda checked: checked and self.single_click_checkbox.setChecked(False)
        )
        layout.insertWidget(layout.count() - 1, behavior_group)

        executable_group = QGroupBox(self.tr("Executable Text Files"), self)
        executable_box = QVBoxLayout(executable_group)
        self.executable_text_combo = QComboBox(self)
        for label, value in self.EXECUTABLE_TEXT_OPTIONS:
            self.executable_text_combo.addItem(self.tr(label), value)
        executable_box.addWidget(self.executable_text_combo)
        layout.insertWidget(layout.count() - 1, executable_group)

        trash_group = QGroupBox(self.tr("Trash"), self)
        trash_box = QVBoxLayout(trash_group)
        self.confirm_trash_move_checkbox = QCheckBox(self.tr("Ask before moving files to the Trash"))
        self.confirm_delete_checkbox = QCheckBox(self.tr("Ask before emptying the Trash or deleting files"))
        self.show_delete_bypass_checkbox = QCheckBox(self.tr("Include a Delete command that bypasses Trash"))
        self.delete_key_bypass_checkbox = QCheckBox(self.tr("Bypass the Trash when the Delete key is pressed"))
        for widget in (
            self.confirm_trash_move_checkbox,
            self.confirm_delete_checkbox,
            self.show_delete_bypass_checkbox,
            self.delete_key_bypass_checkbox,
        ):
            trash_box.addWidget(widget)
        layout.insertWidget(layout.count() - 1, trash_group)

        media_group = QGroupBox(self.tr("Media Handling"), self)
        media_box = QVBoxLayout(media_group)
        self.media_auto_mount_checkbox = QCheckBox(self.tr("Automatically mount removable media when inserted and on startup"))
        self.media_auto_open_checkbox = QCheckBox(self.tr("Automatically open a folder for automounted media"))
        self.media_prompt_autorun_checkbox = QCheckBox(self.tr("Prompt or autorun/autostart programs when media are inserted"))
        self.media_close_on_unmount_checkbox = QCheckBox(self.tr("Automatically close the device's tab, pane, or window when a device is unmounted or ejected"))
        self.media_detect_suggest_checkbox = QCheckBox(self.tr("Detect content of media and suggest application to open"))
        for widget in (
            self.media_auto_mount_checkbox,
            self.media_auto_open_checkbox,
            self.media_prompt_autorun_checkbox,
            self.media_close_on_unmount_checkbox,
            self.media_detect_suggest_checkbox,
        ):
            media_box.addWidget(widget)
        layout.insertWidget(layout.count() - 1, media_group)

        bulk_group = QGroupBox(self.tr("Bulk Rename"), self)
        bulk_form = QFormLayout(bulk_group)
        self.bulk_rename_command_edit = QLineEdit(self)
        bulk_form.addRow(self.tr("Command to invoke when renaming multiple items:"), self.bulk_rename_command_edit)
        layout.insertWidget(layout.count() - 1, bulk_group)

    def _build_display_page(self):
        layout = self._add_page("Display")

        captions_group = QGroupBox(self.tr("Icon Captions"), self)
        captions_form = QFormLayout(captions_group)
        self.icon_caption_combos = []
        for _index in range(3):
            combo = QComboBox(self)
            for label, value in self.ICON_CAPTION_FIELDS:
                combo.addItem(self.tr(label), value)
            self.icon_caption_combos.append(combo)
            captions_form.addRow(combo)
        layout.insertWidget(layout.count() - 1, captions_group)

        date_group = QGroupBox(self.tr("Date"), self)
        date_form = QFormLayout(date_group)
        self.date_format_edit = QLineEdit(self)
        self.date_monospace_checkbox = QCheckBox(self.tr("Use a monospace font"))
        date_form.addRow(self.tr("Format:"), self.date_format_edit)
        date_form.addRow("", self.date_monospace_checkbox)
        layout.insertWidget(layout.count() - 1, date_group)

        title_group = QGroupBox(self.tr("Window and Tab Titles"), self)
        title_form = QFormLayout(title_group)
        self.title_full_path_checkbox = QCheckBox(self.tr("Show the full path in the title bar and tab bars"))
        title_form.addRow("", self.title_full_path_checkbox)
        layout.insertWidget(layout.count() - 1, title_group)

        size_group = QGroupBox(self.tr("File Size"), self)
        size_form = QFormLayout(size_group)
        self.file_size_prefix_combo = QComboBox(self)
        for label, value in self.FILE_SIZE_PREFIX_OPTIONS:
            self.file_size_prefix_combo.addItem(self.tr(label), value)
        size_form.addRow(self.tr("Prefixes:"), self.file_size_prefix_combo)
        layout.insertWidget(layout.count() - 1, size_group)

        properties_group = QGroupBox(self.tr("File Properties"), self)
        properties_box = QVBoxLayout(properties_group)
        self.advanced_permissions_checkbox = QCheckBox(self.tr("Show advanced permissions in the file property dialog"))
        properties_box.addWidget(self.advanced_permissions_checkbox)
        layout.insertWidget(layout.count() - 1, properties_group)

        move_copy_group = QGroupBox(self.tr("Move/Copy To Menu"), self)
        move_copy_box = QVBoxLayout(move_copy_group)
        self.move_copy_bookmarks_checkbox = QCheckBox(self.tr("List bookmarks in the menu"))
        self.move_copy_devices_checkbox = QCheckBox(self.tr("List devices and network locations in the menu"))
        move_copy_box.addWidget(self.move_copy_bookmarks_checkbox)
        move_copy_box.addWidget(self.move_copy_devices_checkbox)
        layout.insertWidget(layout.count() - 1, move_copy_group)

    def _build_list_columns_page(self):
        layout = self._add_page("List Columns")
        row = QHBoxLayout()
        self.list_columns_tree = QTreeWidget(self)
        self.list_columns_tree.setHeaderHidden(True)
        row.addWidget(self.list_columns_tree, 1)

        buttons = QVBoxLayout()
        self.column_move_up_button = QPushButton(self.tr("Move Up"), self)
        self.column_move_down_button = QPushButton(self.tr("Move Down"), self)
        self.column_use_default_button = QPushButton(self.tr("Use Default"), self)
        self.column_move_up_button.clicked.connect(lambda: self._move_current_tree_item(self.list_columns_tree, -1))
        self.column_move_down_button.clicked.connect(lambda: self._move_current_tree_item(self.list_columns_tree, 1))
        self.column_use_default_button.clicked.connect(self._reset_list_columns_defaults)
        buttons.addWidget(self.column_move_up_button)
        buttons.addWidget(self.column_move_down_button)
        buttons.addWidget(self.column_use_default_button)
        buttons.addStretch(1)
        row.addLayout(buttons)
        layout.insertLayout(layout.count() - 1, row)

    def _build_preview_page(self):
        layout = self._add_page("Previewable Files")

        preview_group = QGroupBox(self.tr("Previewable Files"), self)
        preview_form = QFormLayout(preview_group)
        self.preview_thumbnails_combo = QComboBox(self)
        self.preview_folder_counts_combo = QComboBox(self)
        for label, value in self.THUMBNAIL_OPTIONS:
            self.preview_thumbnails_combo.addItem(self.tr(label), value)
            self.preview_folder_counts_combo.addItem(self.tr(label), value)
        self.preview_inherit_checkbox = QCheckBox(self.tr("Inherit thumbnail visibility from parent"))
        self.preview_max_size_combo = QComboBox(self)
        for size_mb in (1, 2, 5, 10, 25, 50, 100):
            self.preview_max_size_combo.addItem(f"{size_mb} MB", size_mb)
        preview_form.addRow(self.tr("Show thumbnails:"), self.preview_thumbnails_combo)
        preview_form.addRow("", self.preview_inherit_checkbox)
        preview_form.addRow(self.tr("Only for files smaller than:"), self.preview_max_size_combo)
        layout.insertWidget(layout.count() - 1, preview_group)

        folder_group = QGroupBox(self.tr("Folders"), self)
        folder_form = QFormLayout(folder_group)
        folder_form.addRow(self.tr("Count number of items:"), self.preview_folder_counts_combo)
        layout.insertWidget(layout.count() - 1, folder_group)

        tooltip_group = QGroupBox(self.tr("Tooltips"), self)
        tooltip_box = QVBoxLayout(tooltip_group)
        self.preview_tooltips_icon_checkbox = QCheckBox(self.tr("Show tooltips in icon and compact views"))
        self.preview_tooltips_list_checkbox = QCheckBox(self.tr("Show tooltips in list views"))
        self.preview_tooltips_desktop_checkbox = QCheckBox(self.tr("Show tooltips on the desktop"))
        tooltip_box.addWidget(self.preview_tooltips_icon_checkbox)
        tooltip_box.addWidget(self.preview_tooltips_list_checkbox)
        tooltip_box.addWidget(self.preview_tooltips_desktop_checkbox)
        tooltip_box.addWidget(QLabel(self.tr("Select additional information to display in the tooltip:")))
        self.preview_tooltip_field_checks = {}
        for key, label in (
            ("detailed_type", "Detailed file type"),
            ("modified_date", "Modified date"),
            ("created_date", "Created date"),
            ("accessed_date", "Accessed date"),
            ("location", "File or folder location"),
        ):
            checkbox = QCheckBox(self.tr(label), self)
            self.preview_tooltip_field_checks[key] = checkbox
            tooltip_box.addWidget(checkbox)
        layout.insertWidget(layout.count() - 1, tooltip_group)

    def _build_toolbar_page(self):
        layout = self._add_page("Visible Buttons")
        group = QGroupBox(self.tr("Visible Buttons"), self)
        grid = QGridLayout(group)
        self.toolbar_button_checks = {}
        for index, (key, label) in enumerate(self.TOOLBAR_BUTTON_LABELS):
            checkbox = QCheckBox(self.tr(label), self)
            self.toolbar_button_checks[key] = checkbox
            grid.addWidget(checkbox, index % 7, index // 7)
        layout.insertWidget(layout.count() - 1, group)

    def _build_context_menus_page(self):
        layout = self._add_page("Visible Entries")
        grid = QGridLayout()
        self.context_menu_checks = {}
        titles = {
            "selection": "Selection",
            "background": "Background",
            "icon_view": "Icon View",
            "desktop": "Desktop",
        }
        positions = {
            "selection": (0, 0),
            "background": (0, 1),
            "icon_view": (1, 1),
            "desktop": (2, 1),
        }
        for group_key, entries in self.CONTEXT_GROUPS.items():
            box = QGroupBox(self.tr(titles[group_key]), self)
            box_layout = QVBoxLayout(box)
            checks = {}
            for key, label in entries:
                checkbox = QCheckBox(self.tr(label), self)
                checks[key] = checkbox
                box_layout.addWidget(checkbox)
            self.context_menu_checks[group_key] = checks
            row, col = positions[group_key]
            grid.addWidget(box, row, col)
        layout.insertLayout(layout.count() - 1, grid)
        layout.insertWidget(
            layout.count() - 1,
            QLabel(self.tr("Visible action and extension entries can be configured in the Plugins tab")),
        )

    def _build_plugins_page(self):
        layout = self._add_page("Plugins")

        self.extensions_enabled_checkbox = QCheckBox(self.tr("Enable plugins and extensions"), self)
        layout.insertWidget(layout.count() - 1, self.extensions_enabled_checkbox)

        top_row = QHBoxLayout()
        self.plugin_actions_tree = self._plugin_tree(self.tr("Actions"))
        self.plugin_scripts_tree = self._plugin_tree(self.tr("Scripts"))
        top_row.addWidget(self.plugin_actions_tree, 1)
        top_row.addWidget(self.plugin_scripts_tree, 1)
        layout.insertLayout(layout.count() - 1, top_row)

        self.plugin_extensions_tree = self._plugin_tree(self.tr("Extensions"))
        layout.insertWidget(layout.count() - 1, self.plugin_extensions_tree)

    def _plugin_tree(self, title: str) -> QTreeWidget:
        tree = QTreeWidget(self)
        tree.setHeaderLabels([title])
        tree.setRootIsDecorated(False)
        return tree

    def _zoom_combo(self) -> QComboBox:
        combo = QComboBox(self)
        for percent in self.ZOOM_OPTIONS:
            combo.addItem(f"{percent}%", percent)
        return combo

    def _load_from_config(self):
        self.default_view_combo.setCurrentIndex(self.default_view_combo.findData(self.config.data.get("default_view_mode", "details")))
        self.inherit_view_checkbox.setChecked(bool(self.config.data.get("inherit_view_from_parent", True)))
        self.arrange_items_combo.setCurrentIndex(self.arrange_items_combo.findData(self.config.data.get("default_sort_key", "name")))
        self.reverse_sort_checkbox.setChecked(bool(self.config.data.get("default_sort_descending", False)))
        self.sort_folders_first_checkbox.setChecked(bool(self.config.data.get("sort_folders_first", True)))
        self.sort_favorites_first_checkbox.setChecked(bool(self.config.data.get("sort_favorites_first", True)))
        self._set_combo_data(self.icon_zoom_combo, self.config.data.get("icon_view_zoom_percent", 100))
        self._set_combo_data(self.compact_zoom_combo, self.config.data.get("compact_view_zoom_percent", 100))
        self.compact_equal_width_checkbox.setChecked(bool(self.config.data.get("compact_view_equal_width", False)))
        self._set_combo_data(self.list_zoom_combo, self.config.data.get("list_view_zoom_percent", 50))
        self.tree_show_only_folders_checkbox.setChecked(bool(self.config.data.get("tree_view_show_only_folders", True)))

        single_click = bool(self.config.data.get("open_items_with_single_click", False))
        self.single_click_checkbox.setChecked(single_click)
        self.double_click_checkbox.setChecked(not single_click)
        self.rename_second_click_checkbox.setChecked(bool(self.config.data.get("rename_with_second_click", False)))
        self.open_folder_new_window_checkbox.setChecked(bool(self.config.data.get("open_folders_in_new_window", False)))
        self.always_dual_pane_checkbox.setChecked(bool(self.config.data.get("always_start_dual_pane", False)))
        self.ignore_folder_preferences_checkbox.setChecked(bool(self.config.data.get("ignore_per_folder_view_preferences", False)))
        self.disable_operation_queue_checkbox.setChecked(bool(self.config.data.get("disable_operation_queueing", False)))
        self.blank_area_go_up_checkbox.setChecked(bool(self.config.data.get("double_click_blank_area_go_up", False)))
        self.executable_text_combo.setCurrentIndex(self.executable_text_combo.findData(self.config.data.get("executable_text_handling", "ask")))
        self.confirm_trash_move_checkbox.setChecked(bool(self.config.data.get("confirm_trash_move", False)))
        self.confirm_delete_checkbox.setChecked(bool(self.config.data.get("confirm_delete_or_empty_trash", True)))
        self.show_delete_bypass_checkbox.setChecked(bool(self.config.data.get("show_delete_bypassing_trash", True)))
        self.delete_key_bypass_checkbox.setChecked(bool(self.config.data.get("delete_key_bypasses_trash", False)))
        self.media_auto_mount_checkbox.setChecked(bool(self.config.data.get("media_auto_mount", True)))
        self.media_auto_open_checkbox.setChecked(bool(self.config.data.get("media_auto_open", True)))
        self.media_prompt_autorun_checkbox.setChecked(bool(self.config.data.get("media_prompt_autorun", True)))
        self.media_close_on_unmount_checkbox.setChecked(bool(self.config.data.get("media_close_on_unmount", False)))
        self.media_detect_suggest_checkbox.setChecked(bool(self.config.data.get("media_detect_and_suggest", True)))
        self.bulk_rename_command_edit.setText(str(self.config.data.get("bulk_rename_command", "")))

        icon_fields = list(self.config.data.get("icon_caption_fields", ["none", "size", "date_modified"]))
        for combo, value in zip(self.icon_caption_combos, icon_fields):
            combo.setCurrentIndex(combo.findData(value))
        self.date_format_edit.setText(str(self.config.data.get("date_display_format", "yyyy-MM-dd HH:mm")))
        self.date_monospace_checkbox.setChecked(bool(self.config.data.get("date_use_monospace", True)))
        self.title_full_path_checkbox.setChecked(bool(self.config.data.get("title_show_full_path", False)))
        self.file_size_prefix_combo.setCurrentIndex(self.file_size_prefix_combo.findData(self.config.data.get("file_size_prefix_style", "decimal")))
        self.advanced_permissions_checkbox.setChecked(bool(self.config.data.get("show_advanced_permissions", False)))
        self.move_copy_bookmarks_checkbox.setChecked(bool(self.config.data.get("move_copy_menu_show_bookmarks", True)))
        self.move_copy_devices_checkbox.setChecked(bool(self.config.data.get("move_copy_menu_show_devices", True)))

        self._populate_list_columns()

        self.preview_thumbnails_combo.setCurrentIndex(self.preview_thumbnails_combo.findData(self.config.data.get("preview_show_thumbnails", "local_only")))
        self.preview_inherit_checkbox.setChecked(bool(self.config.data.get("preview_inherit_thumbnail_visibility", False)))
        self._set_combo_data(self.preview_max_size_combo, self.config.data.get("preview_max_file_size_mb", 1))
        self.preview_folder_counts_combo.setCurrentIndex(self.preview_folder_counts_combo.findData(self.config.data.get("preview_folder_item_counts", "local_only")))
        self.preview_tooltips_icon_checkbox.setChecked(bool(self.config.data.get("preview_tooltips_icon_compact", False)))
        self.preview_tooltips_list_checkbox.setChecked(bool(self.config.data.get("preview_tooltips_list", False)))
        self.preview_tooltips_desktop_checkbox.setChecked(bool(self.config.data.get("preview_tooltips_desktop", False)))
        preview_fields = set(self.config.data.get("preview_tooltip_fields", []))
        for key, checkbox in self.preview_tooltip_field_checks.items():
            checkbox.setChecked(key in preview_fields)

        visible_toolbar_buttons = set(self.config.data.get("toolbar_visible_buttons", []))
        for key, checkbox in self.toolbar_button_checks.items():
            checkbox.setChecked(key in visible_toolbar_buttons)

        for group_key, checks in self.context_menu_checks.items():
            visible_entries = set(self.config.data.get(f"context_menu_{group_key}_entries", []))
            for key, checkbox in checks.items():
                checkbox.setChecked(key in visible_entries)

        self.extensions_enabled_checkbox.setChecked(self.config.extensions_enabled)
        self._populate_plugin_tree(self.plugin_actions_tree, self._extensions)
        self._populate_plugin_tree(self.plugin_scripts_tree, [])
        self._populate_plugin_tree(self.plugin_extensions_tree, self._extensions)

    def _set_combo_data(self, combo: QComboBox, value):
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def _populate_list_columns(self):
        self.list_columns_tree.clear()
        order = list(self.config.data.get("list_columns_order", ["name", "size", "type", "modified"]))
        visible = set(self.config.data.get("list_columns_visible", ["name", "size", "type", "modified"]))
        known = {key: label for key, label in self.LIST_COLUMN_LABELS}
        ordered_keys = [key for key in order if key in known]
        ordered_keys.extend(key for key, _label in self.LIST_COLUMN_LABELS if key not in ordered_keys)
        for key in ordered_keys:
            item = QTreeWidgetItem([self.tr(known[key])])
            item.setData(0, Qt.ItemDataRole.UserRole, key)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            item.setCheckState(0, Qt.CheckState.Checked if key in visible else Qt.CheckState.Unchecked)
            self.list_columns_tree.addTopLevelItem(item)
        if self.list_columns_tree.topLevelItemCount():
            self.list_columns_tree.setCurrentItem(self.list_columns_tree.topLevelItem(0))

    def _populate_plugin_tree(self, tree: QTreeWidget, manifests):
        tree.clear()
        enabled = set(self.config.enabled_extensions)
        if not manifests:
            placeholder = QTreeWidgetItem([self.tr("No entries found")])
            placeholder.setFlags(Qt.ItemFlag.ItemIsEnabled)
            tree.addTopLevelItem(placeholder)
            return
        for manifest in manifests:
            item = QTreeWidgetItem([manifest.name])
            item.setData(0, Qt.ItemDataRole.UserRole, manifest.extension_id)
            item.setToolTip(0, manifest.description or manifest.extension_id)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            item.setCheckState(
                0,
                Qt.CheckState.Checked if manifest.extension_id in enabled else Qt.CheckState.Unchecked,
            )
            tree.addTopLevelItem(item)

    def _move_current_tree_item(self, tree: QTreeWidget, offset: int):
        item = tree.currentItem()
        if item is None:
            return
        index = tree.indexOfTopLevelItem(item)
        target_index = index + offset
        if target_index < 0 or target_index >= tree.topLevelItemCount():
            return
        tree.takeTopLevelItem(index)
        tree.insertTopLevelItem(target_index, item)
        tree.setCurrentItem(item)

    def _reset_list_columns_defaults(self):
        self.config.data["list_columns_order"] = ["name", "size", "type", "modified"]
        self.config.data["list_columns_visible"] = ["name", "size", "type", "modified"]
        self._populate_list_columns()

    def _update_font_preview(self):
        if hasattr(self, "font_preview_label"):
            self.font_preview_label.setFont(self.selected_font())

    def _update_startup_location_controls(self):
        if hasattr(self, "startup_location_combo"):
            is_custom = self.startup_location_combo.currentData() == "custom"
            self.startup_custom_path_edit.setEnabled(is_custom)
            self.startup_custom_path_button.setEnabled(is_custom)

    def _browse_startup_folder(self):
        directory = QFileDialog.getExistingDirectory(
            self,
            self.tr("Choose Startup Folder"),
            self.startup_custom_path_edit.text().strip() or "",
        )
        if directory:
            self.startup_custom_path_edit.setText(directory)

    def selected_font(self):
        font = QFont(self.font_family_combo.currentFont())
        _label, weight, italic = self.STYLE_OPTIONS[self.font_style_combo.currentIndex()]
        font.setPointSize(self.font_size_spin.value())
        font.setWeight(weight)
        font.setItalic(italic)
        return font

    def _checked_tree_entries(self, tree: QTreeWidget) -> list[str]:
        values = []
        for index in range(tree.topLevelItemCount()):
            item = tree.topLevelItem(index)
            value = item.data(0, Qt.ItemDataRole.UserRole)
            if value and item.checkState(0) == Qt.CheckState.Checked:
                values.append(str(value))
        return values

    def preferences(self):
        visible_columns = []
        ordered_columns = []
        for index in range(self.list_columns_tree.topLevelItemCount()):
            item = self.list_columns_tree.topLevelItem(index)
            key = str(item.data(0, Qt.ItemDataRole.UserRole))
            ordered_columns.append(key)
            if item.checkState(0) == Qt.CheckState.Checked:
                visible_columns.append(key)

        enabled_extensions = set()
        for tree in (self.plugin_actions_tree, self.plugin_extensions_tree):
            enabled_extensions.update(self._checked_tree_entries(tree))

        return {
            "default_view_mode": self.default_view_combo.currentData(),
            "inherit_view_from_parent": self.inherit_view_checkbox.isChecked(),
            "default_sort_key": self.arrange_items_combo.currentData(),
            "default_sort_descending": self.reverse_sort_checkbox.isChecked(),
            "sort_folders_first": self.sort_folders_first_checkbox.isChecked(),
            "sort_favorites_first": self.sort_favorites_first_checkbox.isChecked(),
            "icon_view_zoom_percent": int(self.icon_zoom_combo.currentData()),
            "icon_text_beside": self.icon_text_beside_checkbox.isChecked(),
            "compact_view_zoom_percent": int(self.compact_zoom_combo.currentData()),
            "compact_view_equal_width": self.compact_equal_width_checkbox.isChecked(),
            "list_view_zoom_percent": int(self.list_zoom_combo.currentData()),
            "tree_view_show_only_folders": self.tree_show_only_folders_checkbox.isChecked(),
            "open_items_with_single_click": self.single_click_checkbox.isChecked(),
            "rename_with_second_click": self.rename_second_click_checkbox.isChecked(),
            "open_folders_in_new_window": self.open_folder_new_window_checkbox.isChecked(),
            "always_start_dual_pane": self.always_dual_pane_checkbox.isChecked(),
            "ignore_per_folder_view_preferences": self.ignore_folder_preferences_checkbox.isChecked(),
            "disable_operation_queueing": self.disable_operation_queue_checkbox.isChecked(),
            "double_click_blank_area_go_up": self.blank_area_go_up_checkbox.isChecked(),
            "executable_text_handling": self.executable_text_combo.currentData(),
            "confirm_trash_move": self.confirm_trash_move_checkbox.isChecked(),
            "confirm_delete_or_empty_trash": self.confirm_delete_checkbox.isChecked(),
            "show_delete_bypassing_trash": self.show_delete_bypass_checkbox.isChecked(),
            "delete_key_bypasses_trash": self.delete_key_bypass_checkbox.isChecked(),
            "media_auto_mount": self.media_auto_mount_checkbox.isChecked(),
            "media_auto_open": self.media_auto_open_checkbox.isChecked(),
            "media_prompt_autorun": self.media_prompt_autorun_checkbox.isChecked(),
            "media_close_on_unmount": self.media_close_on_unmount_checkbox.isChecked(),
            "media_detect_and_suggest": self.media_detect_suggest_checkbox.isChecked(),
            "bulk_rename_command": self.bulk_rename_command_edit.text().strip(),
            "icon_caption_fields": [combo.currentData() for combo in self.icon_caption_combos],
            "date_display_format": self.date_format_edit.text().strip() or "yyyy-MM-dd HH:mm",
            "date_use_monospace": self.date_monospace_checkbox.isChecked(),
            "title_show_full_path": self.title_full_path_checkbox.isChecked(),
            "file_size_prefix_style": self.file_size_prefix_combo.currentData(),
            "show_advanced_permissions": self.advanced_permissions_checkbox.isChecked(),
            "move_copy_menu_show_bookmarks": self.move_copy_bookmarks_checkbox.isChecked(),
            "move_copy_menu_show_devices": self.move_copy_devices_checkbox.isChecked(),
            "list_columns_order": ordered_columns,
            "list_columns_visible": visible_columns,
            "preview_show_thumbnails": self.preview_thumbnails_combo.currentData(),
            "preview_inherit_thumbnail_visibility": self.preview_inherit_checkbox.isChecked(),
            "preview_max_file_size_mb": int(self.preview_max_size_combo.currentData()),
            "preview_folder_item_counts": self.preview_folder_counts_combo.currentData(),
            "preview_tooltips_icon_compact": self.preview_tooltips_icon_checkbox.isChecked(),
            "preview_tooltips_list": self.preview_tooltips_list_checkbox.isChecked(),
            "preview_tooltips_desktop": self.preview_tooltips_desktop_checkbox.isChecked(),
            "preview_tooltip_fields": [
                key for key, checkbox in self.preview_tooltip_field_checks.items()
                if checkbox.isChecked()
            ],
            "toolbar_visible_buttons": [
                key for key, checkbox in self.toolbar_button_checks.items()
                if checkbox.isChecked()
            ],
            "context_menu_selection_entries": [
                key for key, checkbox in self.context_menu_checks["selection"].items()
                if checkbox.isChecked()
            ],
            "context_menu_background_entries": [
                key for key, checkbox in self.context_menu_checks["background"].items()
                if checkbox.isChecked()
            ],
            "context_menu_icon_view_entries": [
                key for key, checkbox in self.context_menu_checks["icon_view"].items()
                if checkbox.isChecked()
            ],
            "context_menu_desktop_entries": [
                key for key, checkbox in self.context_menu_checks["desktop"].items()
                if checkbox.isChecked()
            ],
            "extensions_enabled": self.extensions_enabled_checkbox.isChecked(),
            "enabled_extensions": sorted(enabled_extensions),
            "sidebar_visible": self.config.sidebar_visible,
            "preview_visible": self.config.preview_visible,
            "show_hidden_files": self.config.show_hidden_files,
            "show_file_extensions": self.config.show_file_extensions,
            "selection_checkboxes": self.config.selection_checkboxes,
            "remember_folder_view": self.config.remember_folder_view,
            "window_remember_size": self.config.window_remember_size,
            "window_width": self.config.window_width,
            "window_height": self.config.window_height,
            "startup_location_mode": self.config.startup_location_mode,
            "startup_location_custom_path": self.config.startup_location_custom_path,
            "ui_font_family": self.config.ui_font_family,
            "ui_font_size": self.config.ui_font_size,
            "ui_font_weight": self.config.ui_font_weight,
            "ui_font_italic": self.config.ui_font_italic,
            "preferred_terminal": self.config.preferred_terminal,
        }
