import sys
from selenium import webdriver
from selenium.common.exceptions import WebDriverException, StaleElementReferenceException
import re
import requests
import json
from argparse import ArgumentParser


pattern = re.compile(r"https?:\/\/([\w-]+\.)+[a-z]{2,5}[\w\-\/#\?&]*")


class AppUrl:

    def __init__(self, url_str: str):
        if url_str != None:
            self.url = url_str.split(sep="?")[0].split(sep="#")[0]
            if "#" in url_str:
                self.anchors = [url_str.split(
                    sep="#")[1].split(sep="?")[0]]
            if "?" in url_str:
                self.param_strings = [url_str.split(sep="?")[1]]
        else:
            self.url = ""

    def __eq__(self, other):
        return other and self.url == other.url

    def __hash__(self):
        return hash(self.url)

    def __len__(self):
        return len(self.url)

    def __str__(self):
        val = self.url

        try:
            if len(self.anchors) > 0:
                val += "#" + self.anchors[0]
        except AttributeError:
            pass
        try:
            if len(self.param_strings) > 0:
                val += "?" + self.param_strings[0]
        except AttributeError:
            pass
        return val

    def __repr__(self):
        val = self.url

        try:
            if len(self.anchors) > 0:
                val += "#" + self.anchors[0]
        except AttributeError:
            pass
        try:
            if len(self.param_strings) > 0:
                val += "?" + self.param_strings[0]
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
    response = requests.get(url)
    return [AppUrl(u.group(0)) for u in re.finditer(pattern, response.text)]


def crawler(base_url: AppUrl, scope, driver, **options):
    if "scan_out_of_scope_scripts" not in options:
        options["scan_out_of_scope_scripts"] = True

    urls_to_fetch, fetched_urls = set([base_url]), set()
    while len(urls_to_fetch) > 0:
        app_url = urls_to_fetch.pop()
        try:
            driver.get(app_url.url)
        except WebDriverException:
            continue
        fetched_urls.add(app_url)
        links = set()

        for el in driver.find_elements_by_tag_name("a"):
            try:
                link = AppUrl(el.get_attribute("href"))
                if len(link) > 0 and in_scope(scope, link.url) and link not in fetched_urls.union(urls_to_fetch):
                    if options["verbosity"]:
                        print(link)
                    links.add(link)
            except StaleElementReferenceException:
                continue

        for script in driver.find_elements_by_tag_name("script"):
            try:
                src = AppUrl(script.get_attribute("src"))

                # shorthand for options["scan_out_of_scope_scripts"]
                opt = options["scan_out_of_scope_scripts"]
                if len(src) > 0 and ((not opt and in_scope(scope, src.url)) or opt):
                    new_links = [link for link in get_links_in_script(
                        src) if in_scope(scope, link.url) and link not in fetched_urls.union(links).union(urls_to_fetch) and len(link) > 0]
                    if len(new_links) > 0:
                        if options["verbosity"]:
                            print(
                                "\n".join([str(l) for l in new_links if l not in links and l not in urls_to_fetch and len(l) > 0]))

                        links.update(new_links)
            except StaleElementReferenceException:
                continue

        urls_to_fetch.update(links)
    return fetched_urls


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
    try:
        crawler(AppUrl(url), scope, driver, **options)
    except Exception as e:
        print(e, file=sys.stderr)
        driver.close()
        sys.exit(-1)

    except KeyboardInterrupt:
        driver.close()
        sys.exit(-1)
    finally:
        driver.close()
