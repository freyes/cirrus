import threading
from cirrus.conn import EC2Connection
from gi.repository import GObject


class ListInstancesThread(threading.Thread, GObject.GObject):

    __gsignals__ = {
        'data-arrived': (GObject.SIGNAL_RUN_LAST, GObject.TYPE_NONE,
                         (GObject.TYPE_PYOBJECT,))
        }

    def __init__(self, account, cols, region=None, filters=None):
        threading.Thread.__init__(self)
        GObject.GObject.__init__(self)

        self.account = account
        self.region = region
        self.filters = filters
        self.instance_ids = None
        self.cols = cols

    def run(self):
        conn = EC2Connection(self.account, self.region)
        print "ass"
        reservations = conn.get_all_instances(instance_ids=self.instance_ids,
                                              filters=self.filters)

        instances = []
        for r in reservations:
            for instance in r.instances:
                row = []
                for item in self.cols:
                    if "transform" in item:
                        value = item["transform"](instance)
                    else:
                        value = getattr(instance, item["field"], "-")

                    row.append(value)
                instances.append(row)

        print "we are going to emit"
        self.emit('data-arrived', instances)

GObject.type_register(ListInstancesThread)
