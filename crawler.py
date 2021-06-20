import sys
from selenium import webdriver
from selenium.common.exceptions import WebDriverException, StaleElementReferenceException
import re
import requests
from requests.exceptions import RequestException
import json
from argparse import ArgumentParser


pattern = re.compile(r"https?:\/\/([\w\-]+\.)+[a-z]{2,5}[^\s\"\']*")


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


def in_scope(scope, url):
    included = False
    try:
        for inc in scope["include"]:
            if re.match(inc, url):
                included = True
                break
    except KeyError:
        return False
    if not included:
        return False

    try:
        for ex in scope["exclude"]:
            if re.match(ex, url):
                return False
        return True
    except KeyError:
        return True


def get_links_in_script(url):
    try:
        response = requests.get(url)
        return [AppUrl(u.group(0)) for u in re.finditer(pattern, response.text)]
    except RequestException:
        return []


def get_robots_file_urls(path: str, exact_path=False):
    root_url = re.match(
        r"https?:\/\/([\w-]+\.)+[a-z]{2,5}", path).group(0)
    if exact_path:
        effective_url = path
    else:
        effective_url = root_url+"/robots.txt"

    try:
        response = requests.get(effective_url)
        disallowed = [line[len("Disallow:"):].strip(
            "\r") for line in response.text.split(sep="\n") if line.startswith("Disallow")]
        allowed = [line[len("Allow:"):].strip("\r") for line in response.text.split(
            sep="\n") if line.startswith("Allow")]
        return [AppUrl(f"{root_url}/{line}") for line in disallowed + allowed if not "*" in line]
    except RequestException:
        return []


def get_sitemap_file(path):
    response = requests.get(path)
    print(response.text)


class Crawler:

    def __init__(self, base_urls: list[AppUrl], scope, driver, on_url_found=None, **options):
        self.base_urls = base_urls
        self.scope = scope
        self.driver = driver
        self.options = options
        self.urls_to_fetch, self.fetched_urls = set(self.base_urls), set()
        self.on_url_found = on_url_found
        self.__parse_options()

    def __parse_options(self):
        if "scan_all_scripts" not in self.options:
            self.options["scan_all_scripts"] = True

    def pause(self):
        self.__running = False

    def crawl(self):
        self.__running = True
        while len(self.urls_to_fetch) > 0 and self.__running:
            app_url = self.urls_to_fetch.pop()
            try:
                self.driver.get(app_url.url)
            except WebDriverException:
                continue
            finally:
            	self.fetched_urls.add(app_url)
            links = set()

            registered_links = dict()

            for el in set(self.driver.find_elements_by_tag_name("a")):
                try:
                    link = AppUrl(el.get_attribute("href"))
                    if len(link) > 0 and in_scope(self.scope, link.url) and link not in self.fetched_urls.union(self.urls_to_fetch):
                        if "verbosity" in self.options and self.options["verbosity"]:
                            print(link)
                        if callable(self.on_url_found):
                            self.on_url_found(link)
                        links.add(link)
                    elif len(link) > 0 and in_scope(self.scope, link.url) and link in self.fetched_urls.union(self.urls_to_fetch):
                        if link.url in registered_links:
                            registered_links[link.url].merge(link)
                        else:
                            registered_links[link.url] = link
                except StaleElementReferenceException:
                    continue

            for script in set(self.driver.find_elements_by_tag_name("script")):
                try:
                    src = AppUrl(script.get_attribute("src"))

                    # shorthand for options["scan_all_scripts"]
                    opt = self.options["scan_all_scripts"]
                    if len(src) > 0 and ((not opt and in_scope(self.scope, src.url)) or opt):

                        found_links = set([link for link in get_links_in_script(src) if in_scope(
                            self.scope, link.url)])

                        new_links = [link for link in found_links if link not in self.fetched_urls.union(
                            links).union(self.urls_to_fetch) and len(link) > 0]
                        if len(new_links) > 0:

                            for link in [l for l in new_links if l not in links and l not in self.urls_to_fetch and len(l) > 0]:
                                if "verbosity" in self.options and self.options["verbosity"]:
                                    print(link)
                                if callable(self.on_url_found):
                                    self.on_url_found(link)

                            links.update(new_links)

                        for link in [link for link in found_links if link in self.fetched_urls.union(
                                links).union(self.urls_to_fetch)]:
                            if link.url in registered_links:
                                registered_links[link.url].merge(link)
                            else:
                                registered_links[link.url] = link

                except StaleElementReferenceException:
                    continue

            self.urls_to_fetch.update(links)


def parseArgs():
    parser = ArgumentParser()
    parser.add_argument(
        "-b", "--browser", help="the browser to use", default="firefox", type=str)
    parser.add_argument(
        "-p", "--browser-path",
        help="the path to the browser driver",
        default="geckodriver",
        type=str
    )

    parser.add_argument("-s", "--scope",
                        help="the path to the json file with the scope", required=True, type=str)
    parser.add_argument("url", help="the url to crawl at", type=str)

    parser.add_argument(
        "--scan-all-scripts", help="scan all scripts for in scope urls even out of scope scripts", default=True, type=bool)

    args = parser.parse_args()

    if args.browser == "chrome":
        opt = webdriver.ChromeOptions()
        opt.headless = True
        if args.browser_path != "geckodriver":
            driver = webdriver.Chrome(
                executable_path=args.browser_path, options=opt)
        else:
            driver = webdriver.Chrome()
    else:
        opt = webdriver.FirefoxOptions()
        opt.headless = True
        driver = webdriver.Firefox(
            executable_path=args.browser_path, options=opt)

    options = {}
    options["scan_out_of_scope_scripts"] = args.scan_all_scripts

    scope = json.loads(open(args.scope).read())

    return args.url, scope, driver, options


if __name__ == "__main__":
    url, scope, driver, options = parseArgs()
    options["verbosity"] = True
    urls = [AppUrl(url)]

    try:
        urls += get_links_in_script(url)
        crawler = Crawler(urls, scope, driver, **options)

        crawler.crawl()
    except Exception as e:
        print(e, file=sys.stderr)

    except BaseException:
        pass

    finally:
        print("closing driver...", file=sys.stderr)
        driver.close()
