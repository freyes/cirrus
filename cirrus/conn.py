import urlparse
from cirrus.config import settings
from cirrus.exception import AccountError
from libcloud.compute.types import Provider
from libcloud.compute.providers import get_driver


class Account(object):
    def __init__(self, name):
        self.name = name
        try:
            self.access_key = settings["accounts"][name]["access_key"]
            self.secret_key = settings["accounts"][name]["secret_key"]
            self.type = settings["accounts"][name].get("type", "").upper()
            self.endpoint = settings["accounts"][name].get("endpoint")

            if self.endpoint:
                parsed = urlparse.urlparse(self.endpoint)
                self.secure = (parsed.scheme == "https")
                self.host = parsed.hostname
                self.port = parsed.port
        except KeyError, ex:
            raise
            raise AccountError("missing %s from account %s" % (ex, name))


class Adapter(object):

    def __init__(self, account, region=None):
        if isinstance(account, basestring):
            self.account = Account(account)
        else:
            self.account = account

        self.driver_klass = get_driver(getattr(Provider, self.account.type))
        kwargs = {}
        if self.account.type == "OPENSTACK":
            kwargs["secure"] = self.account.secure
            kwargs["host"] = self.account.host
            kwargs["ex_force_auth_url"] = self.account.endpoint + "/tokens"
            kwargs["port"] = self.account.port

        print kwargs

        self.conn = self.driver_klass(self.account.access_key,
                                      self.account.secret_key,
                                      **kwargs)
