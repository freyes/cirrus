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
from gi.repository import GObject
from gi.repository import Vte
from gi.repository import Gdk
from gi.repository import GdkPixbuf
from gi.repository import GLib

log = logging.getLogger("app")

_HERE = os.path.dirname(os.path.abspath(__file__))

PIXMAP_PATH = os.path.join(_HERE, "ui", "pixmaps")
APPNAME_SHORT = "cirrus"

state_images = {"running": "state-green.png",
                "stopped": "state-red.png",
                "stopping": "state-red.png",
                "terminated": "state-red.png",
                "pending": "state-yellow.png",
                "shutting-down": "state-yellow.png",
                }


def _get_image_path(name):
    return os.path.join(PIXMAP_PATH, name)


def instance_state_to_pixbuf(instance):
    image_name = state_images.get(instance.extra.get("status"),
                                  "state-yellow.png")
    pixbuf = GdkPixbuf.Pixbuf.new_from_file(_get_image_path(image_name))
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


class TabLabel(Gtk.Box):
    __gsignals__ = {
        "close-clicked": (GObject.SIGNAL_RUN_FIRST,
                          GObject.TYPE_NONE, ()),
    }

    def __init__(self, label_text):
        Gtk.Box.__init__(self)
        self.set_orientation(Gtk.Orientation.HORIZONTAL)
        self.set_spacing(5)

        icon = Gtk.Image()
        icon.set_from_file(_get_image_path('terminal-32x32.png'))
        self.pack_start(icon, False, False, 0)

        label = Gtk.Label(label_text)
        self.pack_start(label, True, True, 0)

        button = Gtk.Button()
        button.set_relief(Gtk.ReliefStyle.NONE)
        button.set_focus_on_click(False)
        button.add(Gtk.Image.new_from_stock(Gtk.STOCK_CLOSE,
                                            Gtk.IconSize.MENU))
        button.connect("clicked", self.button_clicked)
        data = ".button {\n" \
               "-GtkButton-default-border : 0px;\n" \
               "-GtkButton-default-outside-border : 0px;\n" \
               "-GtkButton-inner-border: 0px;\n" \
               "-GtkWidget-focus-line-width : 0px;\n" \
               "-GtkWidget-focus-padding : 0px;\n" \
               "padding: 0px;\n" \
               "}"

        provider = Gtk.CssProvider()
        provider.load_from_data(data)
        button.get_style_context().add_provider(provider, 600)
        self.pack_start(button, False, False, 0)
        self.show_all()

    def button_clicked(self, button, data=None):
        self.emit("close-clicked")


class ConnectionTab(Vte.Terminal):
    """
    Class to represent a notebook tab with a ssh connection
    """
    def __init__(self, instance, container, builder):
        self.instance = instance
        self.container = container
        self.builder = builder

        Vte.Terminal.__init__(self)

    def get_connection_details(self):
        return (self.builder.get_object(
            'connection_username').get_buffer().get_text(),
            self.builder.get_object('connection_key').get_filename(),
            self.builder.get_object('instance_ipaddr'))

    def get_command(self):
        (username, key_filename, ip_address) = self.get_connection_details()

        command = ["ssh", "-o StrictHostKeyChecking=no"]
        if username:
            command.append('-l%s' % username)

        if key_filename:
            command.append('-i%s' % key_filename)

        iter_ = ip_address.get_active_iter()
        model = ip_address.get_model()

        ip_address = model[iter_][0]
        command.append(ip_address)

        return command

    def close(self, tab_label, notebook, tab_widget):
        return notebook.remove_page(notebook.page_num(tab_widget))

    def show(self):
        self.fork_command_full(Vte.PtyFlags.DEFAULT,
                               None, self.get_command(),
                               [], GLib.SpawnFlags.SEARCH_PATH, None, None)

        tab_label = TabLabel("Instance: <%s>" % self.instance.name)
        tab_label.connect("close-clicked", self.close,
                          self.container,
                          self)

        self.container.append_page(self, tab_label)
        self.container.show_all()
        self.container.set_current_page(-1)


class ConnectionSettings:
    """
    Class to manage the connection settings window dialog
    """
    def __init__(self, instance, builder):
        self.instance = instance
        self.builder = builder

    def show(self):
        self.view = self.builder.get_object("connection_settings")
        self.view.connect("delete_event", self.cancel)

        self.connect_btn = self.builder.get_object("connect_btn")
        self.cancel_btn = self.builder.get_object("connect_cancel_btn")

        self.signals()
        self.populate_ip_combo()
        self.view.show_all()

    def populate_ip_combo(self):
        ip_store = Gtk.ListStore(str, str)

        for ip_addr in self.instance.ip_addresses:
            ip_store.append([ip_addr, ip_addr])

        combo = self.builder.get_object("instance_ipaddr")
        model = combo.get_model()

        if model is not None:
            model.clear()

        combo.set_model(ip_store)
        combo.set_active(0)

    def signals(self):
        self.connect_handler = self.connect_btn.connect("clicked",
                                                        self.connect)
        self.cancel_handler = self.cancel_btn.connect("clicked",
                                                      self.cancel)

    def connect(self, widget):
        notebook = self.builder.get_object('notebook1')
        self.tab = ConnectionTab(self.instance,
                                 notebook,
                                 self.builder)
        self.tab.show()

        #hide the current settings window
        self.cancel(self)

    def cancel(self, widget):
        self.view.hide()
        if self.connect_handler:
            self.connect_btn.disconnect(
                self.connect_handler)
        if self.cancel_handler:
            self.cancel_btn.disconnect(
                self.cancel_handler)


class InstanceContextMenu(Gtk.Menu):
    """
    Class for manage the right-click context menu item
    """
    def __init__(self, builder, instance):
        Gtk.Menu.__init__(self)
        self.builder = builder
        self.instance = instance
        self.show()

    def show(self):
        state = self.instance.extra.get("status")
        terminal = Gtk.Image()
        terminal.set_from_file(_get_image_path('terminal-32x32.png'))

        connect_menu = Gtk.ImageMenuItem("Connect via SSH (%s)" % state)
        connect_menu.set_image(terminal)
        connect_menu.set_always_show_image(True)

        if state not in ('running', ):
            connect_menu.set_sensitive(False)

        connect_menu.connect("activate", self.connect_clicked)
        self.append(connect_menu)
        self.show_all()

    def connect_clicked(self, widget):
        if not hasattr(self, 'connection_settings'):
            self.connection_settings = ConnectionSettings(self.instance,
                                                          self.builder)
        self.connection_settings.show()


class ConsoleOutputWindow(object):

    def __init__(self, instance, builder):
        self.clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)

        self.builder = builder
        self.instance = instance

        scrolled = Gtk.ScrolledWindow()

        console_buffer = Gtk.TextBuffer()
        console_buffer.set_text(self.instance.console_output)

        textview = Gtk.TextView(buffer=console_buffer)
        textview.set_editable(False)

        scrolled.add(textview)

        panel.pack_start(scrolled, True, True, 5)

        clipboard = self.builder.get_object("console_output_clipboard")
        clipboard.connect("clicked", self.copy_to_clipboard)
        wnd.show_all()

    def copy_to_clipboard(self, widget):
        self.clipboard.clear()
        clipboard_data = self.console_buffer.get_text(
            *self.console_buffer.get_bounds(), include_hidden_chars=True)
        self.clipboard.set_text(clipboard_data, len(clipboard_data))


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

    def on_tree_instances_press_event(self, treeview, event):
        if event.type == Gdk.EventType.BUTTON_PRESS and event.button == 3:
            selection = treeview.get_selection()
            (model, treeiter) = selection.get_selected()

            if treeiter is not None:
                self.popup = InstanceContextMenu(self.view.builder,
                                                 model[treeiter][-1])
                self.popup.popup(None, None, None, None,
                                 event.button, event.time)

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
