import urlparse
import libcloud.security
from cirrus.config import settings
from cirrus.exception import AccountError
from libcloud.compute.types import Provider
from libcloud.compute.providers import get_driver


class Account(object):
    def __init__(self, name):
        self.name = name
        acct = settings["accounts"][name]
        try:
            self.access_key = acct["access_key"]
            self.secret_key = acct["secret_key"]
            self.type = acct.get("type", "").upper()
            self.endpoint = acct.get("endpoint")
            self.verify_ssl = acct.get("verify_ssl", True)

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
            kwargs["ex_force_auth_url"] = self.account.endpoint
            kwargs["ex_force_auth_version"] = '2.0_password'
            libcloud.security.VERIFY_SSL_CERT = self.account.verify_ssl

        self.conn = self.driver_klass(self.account.access_key,
                                      self.account.secret_key,
                                      **kwargs)
