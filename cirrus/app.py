import sys
import gi
import os.path
from cirrus.config import settings
from cirrus.conn import Account, EC2Connection
from cirrus.ec2 import ListInstancesThread

gi.require_version("Gtk", "3.0")

from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GLib

APPNAME_SHORT = "cirrus"


class AppWindowHandlers(object):
    def __init__(self, view):
        self.view = view

    def on_destroy(self, *args, **kwargs):
        Gtk.main_quit()

    def on_account_changed(self, widget):
        model = widget.get_model()
        iter_ = widget.get_active_iter()

        self.view.selected_account = Account(model[iter_][0])
        self.view.populate_instances()


class AppWindow(object):
    INSTANCES_COLS = [{"display_name": "ID", "field": "id"},
                      {"display_name": "Name", "transform": lambda x: x.tags.get("Name", "")},
                      {"display_name": "AMI", "field": "ami_id"},
                      {"display_name": "Type", "field": "instance_type"},
                      {"display_name": "State", "field": "state"},
                      {"display_name": "Security Groups", "field": "id"},
                      {"display_name": "Key Pair Name", "field": "key_name"},
                      ]

    def __init__(self):
        self.selected_account = None
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

    def setup_instances_treeview(self):
        tree = self.builder.get_object("tree_instances")

        for i, col in enumerate(self.INSTANCES_COLS):
            renderer = Gtk.CellRendererText()
            column = Gtk.TreeViewColumn(col["display_name"], renderer, text=i)
            column.set_sort_column_id(i)
            tree.append_column(column)

    def populate_accounts(self):
        name_store = Gtk.ListStore(str, str)

        for account_name in settings["accounts"]:
            name_store.append([account_name, account_name])

        account_combo = self.builder.get_object("cmb_accounts")
        assert account_combo != None

        account_combo.set_model(name_store)

    def populate_instances(self):
        if not self.selected_account:
            print "no selected account"
            return

        t = ListInstancesThread(self.selected_account, self.INSTANCES_COLS)
        t.connect("data-arrived", self.asdf)
        t.start()

    def asdf(self, gobj, instances):
        model = Gtk.ListStore(*[i.get("type", str) for i in self.INSTANCES_COLS])

        for instance in instances:
            model.append(instance)

        tree = self.builder.get_object("tree_instances")
        tree.set_model(model)


class Application(object):
    def __init__(self):
        self.w = AppWindow()

    def start(self):
        GLib.threads_init()
        Gdk.threads_init()
        Gdk.threads_enter()
        Gtk.main()
        Gdk.threads_leave()


def main(argv=None):
    if argv == None:
        argv = sys.argv

    application = Application()
    application.start()


if __name__ == '__main__':
    main()
