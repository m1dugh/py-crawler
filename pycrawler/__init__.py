import logging
from queue import Empty, Full, Queue
from threading import Lock, Thread

from selenium.common.exceptions import (StaleElementReferenceException,
                                        WebDriverException)

from .model import AppUrl
from .utils import in_scope, get_links_in_script, normalize_url, get_page

from bs4 import BeautifulSoup
import requests



class Crawler:

    def __init__(self, base_urls: list[AppUrl], scope, on_url_found=None, **options):
        self.logger = logging.getLogger()
        self.logger.setLevel(options["verbosity"])
        self.base_urls = base_urls
        self.scope = scope
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

    def __crawl_single_page(self, app_url: AppUrl, callback_q: Queue):

        try:
            self.logger.debug(f"fetching page {app_url.url} ...")

            page, infos = get_page(app_url.url)
            link_elements = [normalize_url(app_url.url, el.get("href")) for el in page.find_all(
                "a") if el.get("href") and len(el.get("href")) > 0]
            link_elements = set(
                [AppUrl(link) for link in link_elements if link and in_scope(self.scope, link)])

            script_urls = [normalize_url(app_url.url, el.get("src")) for el in page.find_all(
                "script") if el.get("src") and len(el.get("src")) > 0]
            script_urls = set([AppUrl(url) for url in script_urls if url and (not self.options["scan_all_scripts"] and in_scope(
                self.scope, url)) or self.options["scan_all_scripts"]])

            self.logger.debug(
                f"found {len(script_urls)} scripts in {app_url.url}")

        except requests.RequestException as e:
            logging.warning(e)
        finally:
            self.lock.acquire()
            self.fetched_urls.add(app_url)
            self.lock.release()

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
                self.logger.debug(f"fetching links for page {app_url.url}")
                found_links = set([link for link in get_links_in_script(src) if in_scope(
                    self.scope, link.url) and len(link) > 0])

                self.lock.acquire()
                new_links = [
                    link for link in found_links if link not in self.fetched_urls.union(self.urls_to_fetch)]
                self.lock.release()

                self.logger.debug(
                    f"found {len(new_links)} new links for scripts in {app_url.url}")

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
            self.logger.debug(f"fetched page {app_url.url}")

    def crawl(self):
        t_count = self.options["threads"]
        queue = Queue()
        threads = []

        while len(threads) + len(self.urls_to_fetch) > 0:
            for i in range(t_count - len(threads)):
                if len(self.urls_to_fetch) > 0:
                    self.logger.debug(
                        f"remaining pages to fetch: {len(self.urls_to_fetch)}")
                    threads.append(
                        Thread(target=self.__crawl_single_page, args=(self.urls_to_fetch.pop(), queue), daemon=True))
                    threads[-1].start()

            threads = [t for t in threads if t.is_alive()]

            while callable(self.on_url_found):
                try:
                    self.on_url_found(queue.get_nowait())
                except Empty:
                    break
                except Full:
                    break
