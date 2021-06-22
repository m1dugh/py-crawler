import json
import re
import sys
from argparse import ArgumentParser
from queue import Empty, Full, Queue
from threading import Lock, Thread

from selenium import webdriver
from selenium.common.exceptions import (StaleElementReferenceException,
                                        WebDriverException)

from model import AppUrl
from utils import *

pattern = re.compile(r"https?:\/\/([\w\-]+\.)+[a-z]{2,5}[^\s\"\']*")


class Crawler:

    def __init__(self, base_urls: list[AppUrl], scope, driver, on_url_found=None, **options):
        self.base_urls = base_urls
        self.scope = scope
        self.driver = driver
        self.options = options
        self.urls_to_fetch, self.fetched_urls = set(self.base_urls), set()
        self.on_url_found = on_url_found
        self.lock = Lock()
        self.__parse_options()

    def __parse_options(self):
        if "scan_all_scripts" not in self.options:
            self.options["scan_all_scripts"] = True

        if "threads" not in self.options:
            self.options["threads"] = 5

    def pause(self):
        self.__running = False

    def __crawl_single_page(self, app_url: AppUrl, callback_q: Queue):
        link_elements, script_urls = set(), set()
        try:
            self.lock.acquire()
            self.driver.get(app_url.url)

            for el in self.driver.find_elements_by_tag_name("a"):
                try:
                    link = AppUrl(el.get_attribute("href"))
                    if len(link) > 0 and in_scope(self.scope, link.url):
                        link_elements.add(link)
                except StaleElementReferenceException:
                    continue

            for el in self.driver.find_elements_by_tag_name("script"):
                try:
                    link = AppUrl(el.get_attribute("src"))
                    if len(link) > 0 and in_scope(self.scope, link.url):
                        script_urls.add(link)
                except StaleElementReferenceException:
                    continue

        except WebDriverException as e:
            print(e)
        finally:
            self.lock.release()
            self.fetched_urls.add(app_url)

        registered_links = dict()

        for link in link_elements:
            self.lock.acquire()
            is_new_link = link not in self.urls_to_fetch.union(
                self.urls_to_fetch)
            self.lock.release()

            if is_new_link:
                callback_q.put(link)

                self.lock.acquire()
                self.urls_to_fetch.add(link)
                self.lock.release()
            else:
                if link.url in registered_links:
                    registered_links[link.url].merge(link)
                else:
                    registered_links[link.url] = link

        for src in script_urls:
            opt = self.options["scan_all_scripts"]
            if len(src) > 0 and ((not opt and in_scope(self.scope, src.url)) or opt):

                found_links = set([link for link in get_links_in_script(src) if in_scope(
                    self.scope, link.url) and len(link) > 0])

                self.lock.acquire()
                new_links = [
                    link for link in found_links if link not in self.fetched_urls.union(self.urls_to_fetch)]
                self.lock.release()

                for link in new_links:
                    callback_q.put(link)

                self.lock.acquire()
                self.urls_to_fetch.update(new_links)
                old_links = [
                    link for link in found_links if link in self.fetched_urls.union(self.urls_to_fetch)]
                self.lock.release()

                for link in old_links:
                    if link.url in registered_links:
                        registered_links[link.url].merge(link)
                    else:
                        registered_links[link.url] = link

                if len(registered_links.keys()) > 0:
                    self.fetched_urls = list(self.fetched_urls)
                    for i in range(len(self.fetched_urls)):
                        if self.fetched_urls[i].url in registered_links:
                            self.fetched_urls[i].merge(
                                registered_links[self.fetched_urls[i].url])
                    self.fetched_urls = set(self.fetched_urls)

    def crawl(self):
        self.__running = True
        t_count = self.options["threads"]
        threads = []
        queue = Queue()

        while (len(self.urls_to_fetch) > 0 or len(threads) > 0) and self.__running:

            if len(threads) < t_count:
                for i in range(t_count - len(threads)):
                    if len(self.urls_to_fetch) > 0:
                        p = Thread(target=self.__crawl_single_page, args=(
                            self.urls_to_fetch.pop(), queue), daemon=True)
                        p.start()
                        threads.append(p)

            threads = [t for t in threads if t.is_alive()]

            if callable(self.on_url_found):
                while True:
                    try:
                        self.on_url_found(queue.get_nowait())
                    except Full:
                        break
                    except Empty:
                        break


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
    parser.add_argument("--url", "-u", help="the url to crawl at", type=str, required=True)

    parser.add_argument(
        "--scan-all-scripts", help="scan all scripts for in scope urls even out of scope scripts", default=True, type=bool)

    parser.add_argument("--threads", "-t", default=5,
                         help="the number of concurrent threads", type=int)

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
    options["threads"] = args.threads

    scope = json.loads(open(args.scope).read())

    return args.url, scope, driver, options


if __name__ == "__main__":
    url, scope, driver, options = parseArgs()
    options["verbosity"] = True
    urls = [AppUrl(url)]

    try:
        urls += get_links_in_script(url)
        crawler = Crawler(urls, scope, driver, print, **options)

        crawler.crawl()

    except KeyboardInterrupt:
        pass

    finally:
        print("closing driver...", file=sys.stderr)
        driver.close()
