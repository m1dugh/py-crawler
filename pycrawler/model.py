
class AppUrlMergeError(RuntimeError):

    def __init__(self, *args):
        RuntimeError.__init__(self, *args)


class AppUrl:

    def __init__(self, url_str: str):
        if url_str != None:
            self.url = url_str.split(sep="?")[0].split(sep="#")[0]
            self.anchors, self.params = set(), list()
            self.length = 0
            if "#" in url_str:
                self.anchors.update([url_str.split(
                    sep="#")[1].split(sep="?")[0]])
            if "?" in url_str:
                param_string = url_str.split(sep="?")[1]
                if len(param_string) > 0:
                    self.params.append(dict())
                    for p in param_string.split(sep="&"):
                        parts = p.split(sep="=")
                        if not parts[0].endswith("[]"):
                            if len(parts) == 2:
                                self.params[-1][parts[0]] = parts[1]
                            elif len(parts) == 1:
                                self.params[-1][parts[0]] = None
                        else:
                            if parts[0][:-2] not in self.params[-1]:
                                self.params[parts[0][:-2]] = []

                            if len(parts) == 2:
                                self.params[parts[0][:-2]].append(parts[1])
                            elif len(parts) == 1:
                                self.params[parts[0][:-2]].append(None)
        else:
            self.url = ""

    def merge(self, app_url):
        if not self.url == app_url.url:
            raise AppUrlMergeError
        self.anchors.update(app_url.anchors)
        self.params += app_url.params

    def __eq__(self, other):
        return other and self.url == other.url and [p.keys() for p in self.params] == [p.keys() for p in other.params]

    def __hash__(self):
        return hash(self.url) ^ hash(tuple([",".join(p.keys()) for p in self.params]))

    def __len__(self):
        return len(self.url)

    def __str__(self):
        val = self.url

        if len(self.anchors) > 0:
            val += "#" + list(self.anchors)[0]

        if len(self.params) > 0:
            val += "?" + \
                "&".join([f"{k}={v}" for k, v in self.params[0].items()])

        return val

    def __repr__(self):
        val = self.url

        try:
            if len(self.anchors) > 0:
                val += "#({})".format("|".join(self.anchors))
        except AttributeError:
            pass
        try:
            for p in self.params:
                val += "?{}".format("&".join([f"{k}={v}" for k,
                                    v in p.items()]))
        except AttributeError:
            pass
        return val
