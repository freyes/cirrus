def simple_debug(f):
    def _(self, *args, **kwargs):
        print self.__class__, f.__name__, args, kwargs
        return f(self, *args, **kwargs)
    return _
