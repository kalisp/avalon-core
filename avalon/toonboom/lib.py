import os
import random
import sys
import queue
import shutil
import zipfile
import signal
import threading
import subprocess
import importlib
import logging

from .server import Server
from ..tools import workfiles
from ..vendor.Qt import QtWidgets

self = sys.modules[__name__]
self.server = None
self.pid = None
self.application_path = None
self.callback_queue = None
self.workfile_path = None
self.port = None
self.extension = None
self.application_name = None

# Setup logging.
self.log = logging.getLogger(__name__)
self.log.setLevel(logging.DEBUG)


def execute_in_main_thread(func_to_call_from_main_thread):
    self.callback_queue.put(func_to_call_from_main_thread)


def main_thread_listen():
    callback = self.callback_queue.get()
    callback()


def launch(application_path, zip_file):
    """Setup for Toon Boom application launch.

    Launches Toon Boom application and the server, then starts listening on the
    main thread for callbacks from the server. This is to have Qt applications
    run in the main thread.

    Args:
        application_path (str): Path to application executable.
        zip_file (str): Path to application scene file zipped.
        application_name (str): Application identifier.
    """
    self.port = random.randrange(5000, 6000)
    os.environ["AVALON_TOONBOOM_PORT"] = str(self.port)
    self.application_path = application_path

    self.application_name = "harmony"
    if "storyboard" in application_path.lower():
        self.application_name = "storyboardpro"

    extension_mapping = {"harmony": "xstage", "storyboardpro": "sboard"}
    self.extension = extension_mapping[self.application_name]

    # Launch Harmony.
    os.environ["TOONBOOM_GLOBAL_SCRIPT_LOCATION"] = os.path.dirname(__file__)

    if os.environ.get("AVALON_TOONBOOM_WORKFILES_ON_LAUNCH", False):
        workfiles.show(save=False)

    # No launch through Workfiles happened.
    if not self.workfile_path:
        launch_zip_file(zip_file)

    self.callback_queue = queue.Queue()
    while True:
        main_thread_listen()


def get_local_path(filepath):
    """From the provided path get the equivalent local path."""
    basename = os.path.splitext(os.path.basename(filepath))[0]
    harmony_path = os.path.join(
        os.path.expanduser("~"), ".avalon", self.application_name
    )
    return os.path.join(harmony_path, basename)


def launch_zip_file(filepath):
    """Launch a Harmony application instance with the provided zip file."""
    self.log.debug("Localizing {}".format(filepath))

    local_path = get_local_path(filepath)
    scene_path = os.path.join(
        local_path, os.path.basename(local_path) + "." + self.extension
    )
    extract_zip_file = False
    if os.path.exists(scene_path):
        # Check remote scene is newer than local.
        if os.path.getmtime(scene_path) < os.path.getmtime(filepath):
            shutil.rmtree(local_path)
            extract_zip_file = True
    else:
        extract_zip_file = True

    if extract_zip_file:
        with zipfile.ZipFile(filepath, "r") as zip_ref:
            zip_ref.extractall(local_path)

    # Close existing scene.
    if self.pid:
        os.kill(self.pid, signal.SIGTERM)

    # Stop server.
    if self.server:
        self.server.stop()

    # Launch Avalon server.
    self.server = Server(self.port)
    thread = threading.Thread(target=self.server.start)
    thread.deamon = True
    thread.start()

    # Save workfile path for later.
    self.workfile_path = filepath

    self.log.debug("Launching {}".format(scene_path))
    process = subprocess.Popen([self.application_path, scene_path])
    self.pid = process.pid


def file_extensions():
    return [".zip"]


def has_unsaved_changes():
    if self.server:
        return self.server.send({"function": "scene.isDirty"})["result"]

    return False


def save_file(filepath):
    temp_path = self.get_local_path(filepath)

    if os.path.exists(temp_path):
        shutil.rmtree(temp_path)

    self.server.send(
        {"function": "scene.saveAs", "args": [temp_path]}
    )["result"]

    zip_and_move(temp_path, filepath)

    self.workfile_path = filepath

    func = """function add_path(path)
    {
        var app = QCoreApplication.instance();
        app.watcher.addPath(path);
    }
    add_path
    """

    scene_path = os.path.join(
        temp_path, os.path.basename(temp_path) + "." + self.extension
    )
    self.server.send(
        {"function": func, "args": [scene_path]}
    )


def open_file(filepath):
    launch_zip_file(filepath)


def current_file():
    """Returning None to make Workfiles app look at first file extension."""
    return None


def work_root(session):
    return os.path.normpath(session["AVALON_WORKDIR"]).replace("\\", "/")


def zip_and_move(source, destination):
    """Zip a directory and move to `destination`

    Args:
        - source (str): Directory to zip and move to destination.
        - destination (str): Destination file path to zip file.
    """
    os.chdir(os.path.dirname(source))
    shutil.make_archive(os.path.basename(source), "zip", source)
    shutil.move(os.path.basename(source) + ".zip", destination)
    self.log.debug("Saved \"{}\" to \"{}\"".format(source, destination))


def on_file_changed(path):
    """Threaded zipping and move of the project directory.

    This method is called when the scene file is changed.
    """

    self.log.debug("File changed: " + path)

    if self.workfile_path is None:
        return

    thread = threading.Thread(
        target=zip_and_move, args=(os.path.dirname(path), self.workfile_path)
    )
    thread.start()


def send(request):
    """Public method for sending requests to Toon Boom application."""
    return self.server.send(request)


def show(module_name):
    """Call show on "module_name".

    This allows to make a QApplication ahead of time and always "exec_" to
    prevent crashing.

    Args:
        module_name (str): Name of module to call "show" on.
    """
    # Need to have an existing QApplication.
    app = QtWidgets.QApplication.instance()
    if not app:
        app = QtWidgets.QApplication(sys.argv)

    # Import and show tool.
    module = importlib.import_module(module_name)
    module.show()

    # QApplication needs to always execute, except when publishing.
    if "publish" in module_name:
        return

    app.exec_()


def save_scene():
    """Saves the Toon Boom scene safely.

    The built-in (to Avalon) background zip and moving of the Harmony scene
    folder, interfers with server/client communication by sending two requests
    at the same time. This only happens when sending "scene.saveAll()". This
    method prevents this double request and safely saves the scene.
    """
    # Need to turn off the backgound watcher else the communication with
    # the server gets spammed with two requests at the same time.
    func = """function func()
    {
        var app = QCoreApplication.instance();
        app.avalon_on_file_changed = false;
        scene.saveAll();
        return (
            scene.currentProjectPath() + "/" + scene.currentVersionName()
        );
    }
    func
    """
    scene_path = self.send({"function": func})["result"] + "." + self.extension

    # Manually update the remote file.
    self.on_file_changed(scene_path)

    # Re-enable the background watcher.
    func = """function func()
    {
        var app = QCoreApplication.instance();
        app.avalon_on_file_changed = true;
    }
    func
    """
    self.send({"function": func})