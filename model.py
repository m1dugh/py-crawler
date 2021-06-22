
class AppUrlMergeError(RuntimeError):

    def __init__(self, *args):
        RuntimeError.__init__(self, args)


class AppUrl:

    def __init__(self, url_str: str):
        if url_str != None:
            self.url = url_str.split(sep="?")[0].split(sep="#")[0]
            self.anchors, self.param_strings = set(), set()
            if "#" in url_str:
                self.anchors.update([url_str.split(
                    sep="#")[1].split(sep="?")[0]])
            if "?" in url_str:
                self.param_strings.update([url_str.split(sep="?")[1]])
        else:
            self.url = ""

    def merge(self, app_url):
        if not self.url == app_url.url:
            raise AppUrlMergeError
        self.anchors.update(app_url.anchors)
        self.param_strings.update(app_url.param_strings)

    def __eq__(self, other):
        return other and self.url == other.url

    def __hash__(self):
        return hash(self.url)

    def __len__(self):
        return len(self.url)

    def __str__(self):
        val = self.url

        if len(self.anchors) > 0:
            val += "#" + str(self.anchors)

        if len(self.param_strings) > 0:
            val += "?" + str(self.param_strings)

        return val

    def __repr__(self):
        val = self.url

        try:
            if len(self.anchors) > 0:
                val += "#({})".format("|".join(self.anchors))
        except AttributeError:
            pass
        try:
            if len(self.param_strings) > 0:
                val += "?({})".format("|".join(self.param_strings))
        except AttributeError:
            pass
        return val
