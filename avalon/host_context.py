import os
import sys
import copy
import logging
import traceback
from .pipeline import _validate_signature, find_config
from . import lib, plugin_from_module, api


class Session:
    def __init__(self, data=None):
        if isinstance(data, Session):
            _data = copy.deepcopy(data._data)

        elif isinstance(data, dict):
            _data = data

        elif data is None:
            _data = {}

        else:
            raise TypeError(
                "Unknown data object. {} {}".format(type(data), str(data))
            )

        self._data = _data

    def get(self, key, default=None):
        return self._data.get(key, default)


class HostContext:
    _registered_config = None

    def __init__(self):
        self.log = logging.getLogger(self.__class__.__name__)

        self.registered_plugins = dict()
        self.registered_plugin_paths = dict()
        self.registered_root = None
        self.registered_host = None
        self.registered_event_handlers = dict()
        self._is_installed = False

    @classmethod
    def cls_registered_config(cls):
        if cls._registered_config is None:
            config = find_config()
            signatures = {
                "install": [],
                "uninstall": [],
            }

            _validate_signature(config, signatures)
            cls._registered_config = config

        return cls._registered_config

    @classmethod
    def cls_deregistered_config(cls):
        cls._registered_config = None

    @property
    def registered_config(self):
        return self.cls_registered_config()

    def deregister_config(self):
        """Undo `register_config()`"""
        self.cls_deregistered_config()

    @property
    def is_installed(self):
        return self._is_installed

    def install(self):
        pass

    def register_host(self, host):
        """Register a new host for the current process

        Arguments:
            host (ModuleType): A module implementing the
                Host API interface. See the Host API
                documentation for details on what is
                required, or browse the source code.

        """
        signatures = {
            "ls": []
        }

        _validate_signature(host, signatures)
        self.registered_root = host

    def registered_host(self):
        """Return currently registered host"""
        return self.registered_root

    def deregister_host(self):
        self.registered_root = None

    def register_plugin(self, superclass, obj):
        """Register an individual `obj` of type `superclass`

        Arguments:
            superclass (type): Superclass of plug-in
            obj (object): Subclass of `superclass`

        """

        if superclass not in self.registered_plugins:
            self.registered_plugins[superclass] = list()

        if obj not in self.registered_plugins[superclass]:
            self.registered_plugins[superclass].append(obj)

    def deregister_plugin(self, superclass, plugin):
        """Oppsite of `register_plugin()`"""
        self.registered_plugins[superclass].remove(plugin)

    def register_plugin_path(self, superclass, path):
        """Register a directory of one or more plug-ins

        Arguments:
            superclass (type): Superclass of plug-ins to look for during
                discovery
            path (str): Absolute path to directory in which
                to discover plug-ins

        """

        if superclass not in self.registered_plugin_paths:
            self.registered_plugin_paths[superclass] = list()

        path = os.path.normpath(path)
        if path not in self.registered_plugin_paths[superclass]:
            self.registered_plugin_paths[superclass].append(path)

    def deregister_plugin_path(self, superclass, path):
        """Oppsite of `register_plugin_path()`"""
        self.registered_plugin_paths[superclass].remove(path)

    def register_root(self, root):
        """Register currently active root"""
        self.log.info("Registering root: {}".format(root))
        self.registered_root = root

    def discover(self, superclass):
        """Find and return subclasses of `superclass`"""

        registered = self.registered_plugins.get(superclass) or list()
        plugins = dict()

        # Include plug-ins from registered paths
        for path in self.registered_plugin_paths.get(superclass) or list():
            for module in lib.modules_from_path(path):
                for plugin in plugin_from_module(superclass, module):
                    if plugin.__name__ in plugins:
                        print("Duplicate plug-in found: %s" % plugin)
                        continue

                    plugins[plugin.__name__] = plugin

        for plugin in registered:
            if plugin.__name__ in plugins:
                print("Warning: Overwriting %s" % plugin.__name__)
            plugins[plugin.__name__] = plugin

        return sorted(plugins.values(), key=lambda Plugin: Plugin.__name__)

    def create(self, name, asset, family, options=None, data=None):
        """Create a new instance

        Associate nodes with a subset and family. These nodes are later
        validated, according to their `family`, and integrated into the
        shared environment, relative their `subset`.

        Data relative each family, along with default data, are imprinted
        into the resulting objectSet. This data is later used by extractors
        and finally asset browsers to help identify the origin of the asset.

        Arguments:
            name (str): Name of subset
            asset (str): Name of asset
            family (str): Name of family
            options (dict, optional): Additional options from GUI
            data (dict, optional): Additional data from GUI

        Raises:
            NameError on `subset` already exists
            KeyError on invalid dynamic property
            RuntimeError on host error

        Returns:
            Name of instance

        """

        plugins = list()
        for Plugin in self.discover(api.Creator):
            has_family = family == Plugin.family

            if not has_family:
                continue

            Plugin.log.info(
                "Creating '%s' with '%s'" % (name, Plugin.__name__)
            )

            try:
                plugin = Plugin(name, asset, options, data)
                self.log.debug("Running {}".format(plugin))

                with self.registered_host.maintained_selection():
                    instance = plugin.process()
            except Exception:
                self.log.debug("Plugin discover failed", exc_info=True)
                continue
            plugins.append(plugin)

        assert plugins, "No Creator plug-ins were run, this is a bug"
        return instance
