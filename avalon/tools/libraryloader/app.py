import os
import sys
import time

from .io_nonsingleton import DbConnector
from ...vendor.Qt import QtWidgets, QtCore
from ... import style
from .. import lib as toolslib
from . import lib
from .models import lib as modelslib

from .widgets import (
    SubsetsWidget,
    VersionWidget,
    FamilyListWidget,
    AssetsWidget
)
from ..gui.widgets.lib import preserve_selection, _iter_model_rows

from pypeapp import config

module = sys.modules[__name__]
module.window = None


class Window(QtWidgets.QDialog):
    """Asset loader interface"""

    tool_title = "Library Loader 0.5"
    tool_name = "library_loader"
    signal_project_changed = QtCore.Signal(object)

    def __init__(
        self, parent=None, icon=None, show_projects=False, show_libraries=True
    ):
        super(Window, self).__init__(parent)

        # Enable minimize and maximize for app
        self.setWindowTitle(self.tool_title)
        self.setWindowFlags(QtCore.Qt.Window)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        if icon is not None:
            self.setWindowIcon(icon)
        # self.setAttribute(QtCore.Qt.WA_DeleteOnClose)

        body = QtWidgets.QWidget()
        footer = QtWidgets.QWidget()
        footer.setFixedHeight(20)

        container = QtWidgets.QWidget()

        self.dbcon = DbConnector()
        self.dbcon.install()

        self.show_projects = show_projects
        self.show_libraries = show_libraries

        assets = AssetsWidget(self.dbcon, multiselection=True, parent=self)
        families = FamilyListWidget(self.dbcon, parent=self)
        subsets = SubsetsWidget(
            self.dbcon, tool_name=self.tool_name, parent=self
        )
        version = VersionWidget(self.dbcon, parent=self)

        # Project
        self.combo_projects = QtWidgets.QComboBox()
        self._set_projects(True)
        self.combo_projects.currentTextChanged.connect(self.on_project_change)

        # Create splitter to show / hide family filters
        asset_filter_splitter = QtWidgets.QSplitter()
        asset_filter_splitter.setOrientation(QtCore.Qt.Vertical)
        asset_filter_splitter.addWidget(self.combo_projects)
        asset_filter_splitter.addWidget(assets)
        asset_filter_splitter.addWidget(families)
        asset_filter_splitter.setStretchFactor(1, 65)
        asset_filter_splitter.setStretchFactor(2, 35)

        container_layout = QtWidgets.QHBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        split = QtWidgets.QSplitter()
        split.addWidget(asset_filter_splitter)
        split.addWidget(subsets)
        split.addWidget(version)
        split.setSizes([180, 950, 200])
        container_layout.addWidget(split)

        body_layout = QtWidgets.QHBoxLayout(body)
        body_layout.addWidget(container)
        body_layout.setContentsMargins(0, 0, 0, 0)

        message = QtWidgets.QLabel()
        message.hide()

        footer_layout = QtWidgets.QVBoxLayout(footer)
        footer_layout.addWidget(message)
        footer_layout.setContentsMargins(0, 0, 0, 0)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(body)
        layout.addWidget(footer)

        self.data = {
            "widgets": {
                "families": families,
                "assets": assets,
                "subsets": subsets,
                "version": version,
            },
            "label": {
                "message": message,
            },
            "state": {
                "template": None,
                "locations": list(),
                "context": {
                    "root": None,
                    "project": None,
                    "assets": None,
                    "assetIds": None,
                    "silo": None,
                    "subset": None,
                    "version": None,
                    "representation": None,
                },
            }
        }

        families.active_changed.connect(subsets.set_family_filters)
        assets.selection_changed.connect(self.on_assetschanged)
        assets.refreshButton.clicked.connect(self.on_refresh_clicked)
        subsets.active_changed.connect(self.on_subsetschanged)
        subsets.version_changed.connect(self.on_versionschanged)
        self.signal_project_changed.connect(self.on_projectchanged)

        # Defaults
        self.resize(1330, 700)

        # Set project
        default_project = self.get_default_project()
        if default_project:
            self.signal_project_changed.emit(default_project)

    def on_refresh_clicked(self):
        self._set_projects()

    def _set_projects(self, default=False):
        projects = self.get_filtered_projects()

        project_name = self.combo_projects.currentText()
        if default:
            project_name = self.get_default_project()

        self.combo_projects.clear()
        if len(projects) > 0:
            self.combo_projects.addItems(projects)

        if project_name:
            index = self.combo_projects.findText(
                project_name, QtCore.Qt.MatchFixedString
            )
            if index:
                self.dbcon.activate_project(project_name)
                self.combo_projects.setCurrentIndex(index)

    def get_filtered_projects(self):
        projects = list()
        for project in self.dbcon.projects():
            is_library = project.get('data', {}).get('library_project', False)
            if (
                (is_library and self.show_libraries) or
                (not is_library and self.show_projects)
            ):
                projects.append(project['name'])

        return projects

    def on_project_change(self):
        projects = self.get_filtered_projects()
        project_name = self.combo_projects.currentText()
        if project_name in projects:
            self.dbcon.activate_project(project_name)
        self.refresh()

    def get_default_project(self):
        # looks into presets if any default library is set
        # - returns name of library from presets if exists in db
        # - if was not found or not set then returns first existing project
        # - returns `None` if any project was found in db
        name = None
        presets = config.get_presets().get("tools", {}).get(
            "library_loader", {}
        )
        if self.show_projects:
            name = presets.get('default_project', None)
        if self.show_libraries and not name:
            name = presets.get('default_library', None)

        projects = self.get_filtered_projects()

        if name and name in projects:
            return name
        elif len(projects) > 0:
            return projects[0]
        return None

    @property
    def current_project(self):
        if self.dbcon.active_project().strip() == '':
            return None
        return self.dbcon.active_project()

    def on_projectchanged(self, project_name):
        self.dbcon.Session['AVALON_PROJECT'] = project_name
        lib.refresh_family_config(self.dbcon)
        modelslib.refresh_group_config(self.dbcon)

        # Find the set config
        _config = lib.find_config(self.dbcon)
        if hasattr(_config, "install"):
            _config.install()
        else:
            print("Config `%s` has no function `install`" %
                  _config.__name__)

        self._refresh()
        self._assetschanged()

        title = "{} - {}"
        if self.dbcon.active_project() is None:
            title = title.format(
                self.tool_title,
                "No project selected"
            )
        else:
            title = title.format(
                self.tool_title,
                os.path.sep.join([
                    lib.registered_root(self.dbcon),
                    self.dbcon.active_project()
                ])
            )
        self.setWindowTitle(title)

    # -------------------------------
    # Delay calling blocking methods
    # -------------------------------

    def refresh(self):
        self.echo("Fetching results..")
        toolslib.schedule(self._refresh, 50, channel="mongo")

    def on_assetschanged(self, *args):
        self.echo("Fetching asset..")
        toolslib.schedule(self._assetschanged, 50, channel="mongo")

    def on_subsetschanged(self, *args):
        self.echo("Fetching subset..")
        toolslib.schedule(self._subsetschanged, 50, channel="mongo")

    def on_versionschanged(self, *args):
        self.echo("Fetching version..")
        toolslib.schedule(self._versionschanged, 150, channel="mongo")

    def set_context(self, context, refresh=True):
        self.echo("Setting context: {}".format(context))
        lib.schedule(lambda: self._set_context(context, refresh=refresh),
                     50, channel="mongo")

    # ------------------------------

    def _refresh(self):
        """Load assets from database"""
        if self.current_project is None:
            return
        # Ensure a project is loaded
        project = self.dbcon.find_one({"type": "project"})
        assert project, "This is a bug"

        assets_model = self.data["widgets"]["assets"]
        assets_model.refresh()
        assets_model.setFocus()

        families = self.data["widgets"]["families"]
        families.refresh()

        # Update state
        state = self.data["state"]
        state["template"] = project["config"]["template"]["publish"]
        state["context"]["root"] = lib.registered_root(self.dbcon)
        state["context"]["project"] = project["name"]

    def clear_assets_underlines(self):
        last_asset_ids = self.data["state"]["context"]["assetIds"]
        if not last_asset_ids:
            return

        assets_widget = self.data["widgets"]["assets"]
        id_role = assets_widget.model.ObjectIdRole

        for index in _iter_model_rows(assets_widget.model, 0):
            if index.data(id_role) not in last_asset_ids:
                continue

            assets_widget.model.setData(
                index, [], assets_widget.model.subsetColorsRole
            )

    def _assetschanged(self):
        """Selected assets have changed"""

        assets_widget = self.data["widgets"]["assets"]
        subsets_widget = self.data["widgets"]["subsets"]

        subsets_widget.model.clear()

        self.clear_assets_underlines()

        t1 = time.time()
        asset_docs = assets_widget.get_selected_assets()
        if len(asset_docs) == 0:
            return

        asset_ids = [a["_id"] for a in asset_docs]
        asset_names = [a["name"] for a in asset_docs]
        subsets_widget.model.set_assets(asset_ids)
        subsets_widget.view.setColumnHidden(
            subsets_widget.model.COLUMNS.index("asset"),
            len(asset_ids) < 2
        )

        # # Enforce the columns to fit the data (purely cosmetic)
        # rows = subsets_model.rowCount(QtCore.QModelIndex())
        # for i in range(rows):
        #     subsets.view.resizeColumnToContents(i)

        # Clear the version information on asset change
        self.data['widgets']['version'].set_version(None)

        self.data["state"]["context"]["assets"] = asset_names
        self.data["state"]["context"]["assetIds"] = asset_ids
        self.echo("Duration: %.3fs" % (time.time() - t1))

    def _subsetschanged(self):
        asset_ids = self.data["state"]["context"]["assetIds"]
        # Skip setting colors if not asset multiselection
        if not asset_ids or len(asset_ids) < 2:
            self._versionschanged()
            return

        subsets = self.data["widgets"]["subsets"]
        selected_subsets = subsets.selected_subsets(_merged=True, _other=False)

        asset_models = {}
        asset_ids = []
        for subset_node in selected_subsets:
            asset_ids.extend(subset_node.get("assetIds", []))
        asset_ids = set(asset_ids)

        for subset_node in selected_subsets:
            for asset_id in asset_ids:
                if asset_id not in asset_models:
                    asset_models[asset_id] = []

                color = None
                if asset_id in subset_node.get("assetIds", []):
                    color = subset_node["subsetColor"]

                asset_models[asset_id].append(color)

        self.clear_assets_underlines()

        assets_widget = self.data["widgets"]["assets"]
        indexes = assets_widget.view.selectionModel().selectedRows()

        for index in indexes:
            id = index.data(assets_widget.model.ObjectIdRole)
            if id not in asset_models:
                continue

            assets_widget.model.setData(
                index, asset_models[id], assets_widget.model.subsetColorsRole
            )
        # Trigger repaint
        assets_widget.view.updateGeometries()
        # Set version in Version Widget
        self._versionschanged()

    def _versionschanged(self):

        subsets = self.data["widgets"]["subsets"]
        selection = subsets.view.selectionModel()

        # Active must be in the selected rows otherwise we
        # assume it's not actually an "active" current index.
        version = None
        active = selection.currentIndex()
        if active:
            rows = selection.selectedRows(column=active.column())
            if active in rows:
                node = active.data(subsets.model.NodeRole)
                if (
                    node is not None and
                    not (node.get("isGroup") or node.get("isMerged"))
                ):
                    version = node['version_document']['_id']

        self.data['widgets']['version'].set_version(version)

    def _set_context(self, context, refresh=True):
        """Set the selection in the interface using a context.

        The context must contain `asset` data by name.

        Note: Prior to setting context ensure `refresh` is triggered so that
              the "silos" are listed correctly, aside from that setting the
              context will force a refresh further down because it changes
              the active silo and asset.

        Args:
            context (dict): The context to apply.

        Returns:
            None

        """

        asset = context.get("asset", None)
        if asset is None:
            return

        if refresh:
            # Workaround:
            # Force a direct (non-scheduled) refresh prior to setting the
            # asset widget's silo and asset selection to ensure it's correctly
            # displaying the silo tabs. Calling `window.refresh()` and directly
            # `window.set_context()` the `set_context()` seems to override the
            # scheduled refresh and the silo tabs are not shown.
            self._refresh()

        asset_widget = self.data['model']['assets']
        asset_widget.select_assets(asset)

    def echo(self, message):
        widget = self.data["label"]["message"]
        widget.setText(str(message))
        widget.show()
        print(message)

        toolslib.schedule(widget.hide, 5000, channel="message")

    def closeEvent(self, event):
        # Kill on holding SHIFT
        modifiers = QtWidgets.QApplication.queryKeyboardModifiers()
        shift_pressed = QtCore.Qt.ShiftModifier & modifiers

        if shift_pressed:
            print("Force quitted..")
            self.setAttribute(QtCore.Qt.WA_DeleteOnClose)

        # Kill on holding SHIFT
        modifiers = QtWidgets.QApplication.queryKeyboardModifiers()
        shift_pressed = QtCore.Qt.ShiftModifier & modifiers

        if shift_pressed:
            print("Force quitted..")
            self.setAttribute(QtCore.Qt.WA_DeleteOnClose)

        # self.db.uninstall()

        print("Good bye")
        return super(Window, self).closeEvent(event)


def show(
    debug=False, parent=None, icon=None,
    show_projects=False, show_libraries=True
):
    """Display Loader GUI

    Arguments:
        debug (bool, optional): Run loader in debug-mode,
            defaults to False
        parent (QtCore.QObject, optional): The Qt object to parent to.
        use_context (bool): Whether to apply the current context upon launch

    """
    # Remember window
    if module.window is not None:
        try:
            module.window.show()

            # If the window is minimized then unminimize it.
            if module.window.windowState() & QtCore.Qt.WindowMinimized:
                module.window.setWindowState(QtCore.Qt.WindowActive)

            # Raise and activate the window
            module.window.raise_()             # for MacOS
            module.window.activateWindow()     # for Windows
            module.window.refresh()
            return
        except RuntimeError as e:
            if not e.message.rstrip().endswith("already deleted."):
                raise

            # Garbage collected
            module.window = None

    if debug:
        import traceback
        sys.excepthook = lambda typ, val, tb: traceback.print_last()

    with toolslib.application():
        window = Window(parent, icon, show_projects, show_libraries)
        window.setStyleSheet(style.load_stylesheet())
        window.show()

        module.window = window


def cli(args):

    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("project")

    show(show_projects=True, show_libraries=True)
