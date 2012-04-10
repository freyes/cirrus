import threading
from cirrus.conn import Adapter
from gi.repository import GObject
from gi.repository import Gdk


class ListInstancesThread(threading.Thread, GObject.GObject):

    __gsignals__ = {
        'data-arrived': (GObject.SIGNAL_RUN_LAST, GObject.TYPE_NONE,
                         (GObject.TYPE_PYOBJECT,))
        }

    def __init__(self, account, region=None, filters=None):
        threading.Thread.__init__(self)
        GObject.GObject.__init__(self)

        self.account = account
        self.region = region
        self.filters = filters
        self.instance_ids = None

    def run(self):
        adapter = Adapter(self.account)

        instances = []
        for instance in adapter.conn.list_nodes():
            instances.append(instance)
        Gdk.threads_enter()
        self.emit('data-arrived', instances)
        Gdk.threads_leave()

GObject.type_register(ListInstancesThread)
