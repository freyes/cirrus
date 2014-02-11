import os.path
import logging
from gi.repository import GdkPixbuf

state_images = {"running": "state-green.png",
                0: "state-green.png",
                "stopped": "state-red.png",
                "stopping": "state-red.png",
                "terminated": "state-red.png",
                2: "state-red.png",
                "pending": "state-yellow.png",
                "shutting-down": "state-yellow.png",
                1: "state-yellow.png",
                3: "state-yellow.png",
                4: "state-yellow.png",
                }


class Instance(object):
    def __init__(self, type_, obj):
        self.log = logging.getLogger("Instance")
        for prop in dir(obj):
            if not prop.startswith("__"):
                setattr(self, prop, getattr(obj, prop))

        self._type = type
        self._obj = obj

    @property
    def ip_address(self):
        return ", ".join(self.public_ips)

    @property
    def private_ip_address(self):
        return ", ".join(self.private_ips)

    @property
    def ip_addresses(self):
        """
        Returns a list of all the available ip address ( public, private )
        """
        ip_addrs = []
        for attr in ('ip_address', 'private_ips', 'public_ips', ):
            try:
                ips = getattr(self, attr)
            except AttributeError:
                pass
            else:
                if not isinstance(ips, list):
                    if ips not in (None, ""):
                        ips = ips.split(",")
            for ip in ips:
                ip = ip.strip(" ")
                if ip not in ip_addrs:
                    ip_addrs.append(ip)
        return ip_addrs

    @property
    def key_name(self):
        return self.extra.get("keyname", None)

    @property
    def image_id(self):
        return self.extra.get("imageId", None)

    @property
    def instance_type(self):
        return self.extra.get("instancetype", None)

    @property
    def state_pixbuf(self):
        state = self.state
        if state == 4:
            state = self.extra.get("status", 4)

        image_name = state_images.get(state, "state-yellow.png")
        _here = os.path.dirname(os.path.abspath(__file__))
        fpath = os.path.join(_here, "ui", "pixmaps", image_name)
        pixbuf = GdkPixbuf.Pixbuf.new_from_file(fpath)

        return pixbuf
