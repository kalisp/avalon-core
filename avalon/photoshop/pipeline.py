from .. import api, pipeline
from . import lib, com_objects
from ..vendor import Qt

import pyblish.api


def install(config):
    """Install Photoshop-specific functionality of avalon-core.

    This function is called automatically on calling `api.install(photoshop)`.
    """
    print("Installing Avalon Photoshop...")
    pyblish.api.register_host("photoshop")


def ls():
    """Yields containers from active Photoshop document

    This is the host-equivalent of api.ls(), but instead of listing
    assets on disk, it lists assets already loaded in Photoshop; once loaded
    they are called 'containers'

    Yields:
        dict: container

    """
    pass


class Creator(api.Creator):
    def process(self):
        # Photoshop can have multiple LayerSets with the same name, which does
        # not work with Avalon.
        msg = "Instance with name \"{}\" already exists.".format(self.name)
        for layer in lib.get_layers_in_document():
            if self.name.lower() == layer.Name.lower():
                msg = Qt.QtWidgets.QMessageBox()
                msg.setIcon(Qt.QtWidgets.QMessageBox.Warning)
                msg.setText(msg)
                msg.exec_()
                return False

        # Store selection because adding a group will change selection.
        with lib.maintained_selection() as selection:
            # Create group/layer relationship.
            group = lib.app().ActiveDocument.LayerSets.Add()
            group.Name = self.name

            lib.imprint(group, self.data)

            # Add selection to group.
            if (self.options or {}).get("useSelection"):
                for item in selection:
                    item.Move(group, com_objects.constants().psPlaceAtEnd)

        return group


def containerise(name,
                 namespace,
                 layer_id,
                 context,
                 loader=None,
                 suffix="_CON"):
    """Imprint layer with metadata

    Containerisation enables a tracking of version, author and origin
    for loaded assets.

    Arguments:
        name (str): Name of resulting assembly
        namespace (str): Namespace under which to host container
        layer_id (list): Id of layer to containerise
        context (dict): Asset information
        loader (str, optional): Name of loader used to produce this container.
        suffix (str, optional): Suffix of container, defaults to `_CON`.

    Returns:
        container (str): Name of container assembly

    """

    # Create proper container name
    container = lib.get_layers_by_ids([layer_id])[0]

    data = {
        "schema": "avalon-core:container-2.0",
        "id": pipeline.AVALON_CONTAINER_ID,
        "name": name,
        "namespace": namespace,
        "loader": str(loader),
        "representation": str(context["representation"]["_id"]),
    }

    lib.imprint(container, data)

    return container
