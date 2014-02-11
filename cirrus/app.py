import sys
import gi
import os.path
import logging
import signal
from datetime import datetime
from cirrus.config import settings
from cirrus.conn import Account
from cirrus.ec2 import ListInstancesThread

gi.require_version("Gtk", "3.0")

from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GdkPixbuf
from gi.repository import GLib

log = logging.getLogger("app")
APPNAME_SHORT = "cirrus"

state_images = {"running": "state-green.png",
                "stopped": "state-red.png",
                "stopping": "state-red.png",
                "terminated": "state-red.png",
                "pending": "state-yellow.png",
                "shutting-down": "state-yellow.png",
                }


def instance_state_to_pixbuf(instance):
    image_name = state_images.get(instance.extra.get("status"),
                                  "state-yellow.png")
    _here = os.path.dirname(os.path.abspath(__file__))
    fpath = os.path.join(_here, "ui", "pixmaps", image_name)
    pixbuf = GdkPixbuf.Pixbuf.new_from_file(fpath)

    return pixbuf


def instance_age(instance):

    # 2011-04-26T22:36:27.000Z
    launchdatetime = instance.extra.get("launchdatetime")
    if not launchdatetime:
        return ""

    launch_time = datetime.strptime(launchdatetime,
                                    "%Y-%m-%dT%H:%M:%S.000Z")
    return launch_time.strftime(settings.get("datetime_format",
                                             "%H:%M %m/%d/%Y"))


class ConsoleOutputWindow(object):
    def __init__(self, instance, builder):
        self.builder = builder
        self.instance = instance

        console = instance.get_console_output()
        lbl = self.builder.get_object("lbl_console_output")
        lbl.set_text(console.output)

        wnd = self.builder.get_object("wnd_console_output")
        wnd.show_all()


class AppWindowHandlers(object):
    def __init__(self, view):
        self.view = view

    def on_delete(self, *args, **kwargs):
        Gtk.main_quit()

    def on_account_changed(self, widget):
        model = widget.get_model()
        iter_ = widget.get_active_iter()

        if iter_ is not None:
            self.view.selected_account = Account(model[iter_][0])
            self.view.populate_instances(account_widget=widget)

    def on_toolbtn_view_console_clicked(self, widget):
        tree = self.view.builder.get_object("tree_instances")
        selection = tree.get_selection()
        (model, treeiter) = selection.get_selected()
        if treeiter is None:
            log.debug("No row selected")
            return True
        item = model[treeiter]

        ConsoleOutputWindow(item[-1], self.view.builder)

    def on_toolbtn_refresh_clicked(self, widget):
        self.view.populate_instances()


class AppWindow(object):
    INSTANCES_COLS = [{"display_name": "ID", "field": "id"},
                      {"display_name": "Name", "field": "name"},
                      {"display_name": "AMI", "field": "image_id"},
                      {"display_name": "Type", "field": "instance_type"},
                      {"display_name": "State", "field": "state_pixbuf",
                       "type": GdkPixbuf.Pixbuf,
                       "renderer": Gtk.CellRendererPixbuf(),
                       "sort_col": 5},
                      {"field": "status", "visible": False,
                       "transform": lambda x: x.extra.get("status")},
                      {"display_name": "Security Groups", "field": "id"},
                      {"display_name": "Key Pair Name", "field": "key_name"},
                      {"display_name": "Public IP", "field": "ip_address"},
                      {"display_name": "Private IP",
                       "field": "private_ip_address"},
                      {"display_name": "Age", "transform": instance_age,
                       "sort_col": 11},
                      {"field": "launch_time", "visible": False,
                       "transform": lambda x: x.extra.get("launchdatetime",
                                                          "")},
                      ]

    def __init__(self):
        self.log = logging.getLogger(self.__class__.__name__)
        self.selected_account = None
        self.account_widget = None
        _here = os.path.dirname(os.path.abspath(__file__))
        self.builder_file = os.path.join(_here, "ui", "ui.glade")
        self.builder = Gtk.Builder()
        self.builder.add_from_file(self.builder_file)
        self.builder.connect_signals(AppWindowHandlers(self))
        self.setup_instances_treeview()
        self.populate_accounts()
        self.populate_instances()
        self.window.show_all()

    @property
    def window(self):
        return self.builder.get_object("window1")

    @property
    def statusbar(self):
        return self.builder.get_object("main_statusbar")

    def setup_instances_treeview(self):
        tree = self.builder.get_object("tree_instances")

        for i, col in enumerate(self.INSTANCES_COLS):
            if not col.get("visible", True):
                continue

            renderer = col.get("renderer", Gtk.CellRendererText())

            if isinstance(renderer, Gtk.CellRendererPixbuf):
                column = Gtk.TreeViewColumn()
                column.set_title(col["display_name"])
                column.pack_start(renderer, expand=False)
                column.add_attribute(renderer, "pixbuf", i)
            else:
                column = Gtk.TreeViewColumn(col["display_name"],
                                            renderer, text=i)

            col_number = col.get("sort_col", i)
            column.set_sort_column_id(col_number)
            tree.append_column(column)

    def populate_accounts(self):
        self.log.debug("populating accounts")
        name_store = Gtk.ListStore(str, str)

        for account_name in settings["accounts"]:
            self.log.debug("account found: %s" % account_name)
            name_store.append([account_name, account_name])

        account_combo = self.builder.get_object("cmb_accounts")
        assert account_combo is not None
        account_combo.set_model(name_store)

    def populate_instances(self, account_widget=None):
        self.log.debug("populating instances")
        if not self.selected_account:
            self.log.info("no selected account")
            return

        if account_widget is not None:
            self.account_widget = account_widget

        t = ListInstancesThread(self.selected_account)
        t.connect("data-arrived", self.process_instances)
        t.connect('list-nodes-error', self.manage_error)
        self.log.debug("launched thread to get the instances")
        t.start()

    def process_instances(self, gobj, instances):
        self.log.debug("the instances arrived, processing them...")
        model = Gtk.ListStore(*([i.get("type", str)
                                for i in self.INSTANCES_COLS] + [object]))

        for instance in instances:
            row = []
            for item in self.INSTANCES_COLS:
                if "transform" in item:
                    value = item["transform"](instance)
                else:
                    value = getattr(instance, item["field"], "-")

                row.append(value)
            row.append(instance)
            model.append(row)

        tree = self.builder.get_object("tree_instances")
        tree.set_model(model)
        self.log.debug("instances loaded: %d" % len(instances))

    def raise_error_dialog(self, message):
        dialog = Gtk.MessageDialog(self.window, 0, Gtk.MessageType.ERROR,
                                   Gtk.ButtonsType.OK,
                                   "Error performing operation")
        dialog.format_secondary_text(str(message))
        dialog.run()
        dialog.destroy()

    def manage_error(self, gobj, ex):
        self.log.debug("Error: %s" % ex)

        ctx_id = self.statusbar.get_context_id("MAIN")
        msg_id = self.statusbar.push(ctx_id, str(ex))

        self.raise_error_dialog(ex)

        if self.account_widget is not None:
            #This is a hack to re-enable the same last active item
            #to be re-enabled and clickable.
            self.account_widget.set_active(-1)

        GLib.timeout_add_seconds(10,
                                 lambda: self.statusbar.remove(ctx_id, msg_id))


class Application(object):
    def __init__(self):
        self.w = AppWindow()

    def start(self):
        GLib.threads_init()
        Gdk.threads_init()
        Gdk.threads_enter()
        Gtk.main()
        Gdk.threads_leave()

    def quit_now(self, signum, frame):
        Gtk.main_quit()


def main(argv=None):
    if argv is None:
        argv = sys.argv

    logging.basicConfig(level=logging.DEBUG)
    log.info("Starting application")
    application = Application()
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    application.start()


if __name__ == '__main__':
    main()
