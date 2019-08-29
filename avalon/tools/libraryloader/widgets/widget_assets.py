import contextlib

from ....vendor import qtawesome as awesome
from ....vendor.Qt import QtWidgets, QtCore
from .... import style

from ..models import RecursiveSortFilterProxyModel, AssetModel, AssetView
from ...gui.widgets.lib import _iter_model_rows


class AssetsWidget(QtWidgets.QWidget):
    """A Widget to display a tree of assets with filter

    To list the assets of the active project:
        >>> # widget = AssetWidget()
        >>> # widget.refresh()
        >>> # widget.show()

    """

    assets_refreshed = QtCore.Signal()   # on model refresh
    selection_changed = QtCore.Signal()  # on view selection change
    current_changed = QtCore.Signal()    # on view current index change

    def __init__(self, dbcon, parent):
        super(AssetWidget, self).__init__(parent=parent)
        self.setContentsMargins(0, 0, 0, 0)

        self.dbcon = dbcon

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Tree View
        model = AssetModel(self)
        proxy = RecursiveSortFilterProxyModel()
        proxy.setSourceModel(model)
        proxy.setFilterCaseSensitivity(QtCore.Qt.CaseInsensitive)
        view = AssetView()
        view.setModel(proxy)

        # Header
        header = QtWidgets.QHBoxLayout()

        icon = awesome.icon("fa.refresh", color=style.colors.light)
        refresh = QtWidgets.QPushButton(icon, "")
        refresh.setToolTip("Refresh items")

        filter = QtWidgets.QLineEdit()
        filter.textChanged.connect(proxy.setFilterFixedString)
        filter.setPlaceholderText("Filter assets..")

        header.addWidget(filter)
        header.addWidget(refresh)

        # Layout
        layout.addLayout(header)
        layout.addWidget(view)

        # Signals/Slots
        selection = view.selectionModel()
        selection.selectionChanged.connect(self.selection_changed)
        selection.currentChanged.connect(self.current_changed)
        self.parent_widget.signal_project_changed.connect(self.refresh)

        self.refreshButton = refresh
        self.model = model
        self.proxy = proxy
        self.view = view

    def collect_data(self):
        project = self.dbcon.find_one({'type': 'project'})
        asset = self.dbcon.find_one({'_id': self.get_active_asset()})

        try:
            index = self.task_view.selectedIndexes()[0]
            task = self.task_model.itemData(index)[0]
        except Exception:
            task = None
        data = {
            'project': project['name'],
            'asset': asset['name'],
            'parents': self.get_parents(asset),
            'task': task
        }
        return data

    def get_parents(self, entity):
        output = []
        if entity.get('data', {}).get('visualParent', None) is None:
            return output
        parent = self.dbcon.find_one({'_id': entity['data']['visualParent']})
        output.append(parent['name'])
        output.extend(self.get_parents(parent))
        return output

    def _refresh_model(self):
        self.model.refresh()
        self.assets_refreshed.emit()

    def refresh(self):
        self._refresh_model()

    def get_active_asset(self):
        """Return the asset id the current asset."""
        current = self.view.currentIndex()
        return current.data(self.model.ObjectIdRole)

    def get_active_index(self):
        return self.view.currentIndex()

    def get_selected_assets(self):
        """Return the assets' ids that are selected."""
        selection = self.view.selectionModel()
        rows = selection.selectedRows()
        return [row.data(self.model.ObjectIdRole) for row in rows]

    def select_assets(self, assets, expand=True):
        """Select assets by name.

        Args:
            assets (list): List of asset names
            expand (bool): Whether to also expand to the asset in the view

        Returns:
            None

        """
        # TODO: Instead of individual selection optimize for many assets

        assert isinstance(assets,
                          (tuple, list)), "Assets must be list or tuple"

        # Clear selection
        selection_model = self.view.selectionModel()
        selection_model.clearSelection()

        # Select
        mode = selection_model.Select | selection_model.Rows
        for index in _iter_model_rows(self.proxy,
                                      column=0,
                                      include_root=False):
            data = index.data(self.model.NodeRole)
            name = data['name']
            if name in assets:
                selection_model.select(index, mode)

                if expand:
                    self.view.expand(index)

                # Set the currently active index
                self.view.setCurrentIndex(index)
