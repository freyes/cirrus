from cirrus.config import settings
from cirrus.exception import AccountError
from boto.ec2.connection import EC2Connection as BotoEC2Connection


class Account(object):
    def __init__(self, name):
        self.name = name
        try:
            self.access_key = settings["accounts"][name]["access_key"]
            self.secret_key = settings["accounts"][name]["secret_key"]
            self.account_id = settings["accounts"][name]["account_id"]
        except KeyError, ex:
            raise
            raise AccountError("missing %s from account %s" % (ex, name))


class EC2Connection(BotoEC2Connection):

    def __init__(self, account, region=None):
        if isinstance(account, basestring):
            self.account = Account(account)
        else:
            self.account = account

        super(EC2Connection, self).__init__(self.account.access_key,
                                            self.account.secret_key)

        if region != None:
            region = self.get_all_regions(filters={"region_name": region})

            super(EC2Connection, self).__init__(self.account.access_key,
                                                self.account.secret_key,
                                                region=region)
