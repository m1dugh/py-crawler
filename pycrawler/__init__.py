import logging
from queue import Empty, Full, Queue
from threading import Lock, Thread
from typing import Iterable

from .utils import in_scope, get_links_in_script, normalize_url, get_page, extract_pure_url

import requests


class Crawler:

    def __init__(self, base_urls: Iterable[str], scope, on_url_found=None, **options):
        self.logger = logging.getLogger("pycrawler.Crawler")
        self.logger.setLevel(options["verbosity"])
        self.scope = scope
        self.options = options
        self.urls_to_fetch, self.fetched_urls, self.error_urls = set(
            base_urls), dict(), dict()
        self.on_url_found = on_url_found
        self.lock = Lock()
        self.__parse_options()

    def __parse_options(self):
        if "scan_all_scripts" not in self.options:
            self.options["scan_all_scripts"] = True

        if "threads" not in self.options:
            self.options["threads"] = 5

        if "verbosity" not in self.options:
            self.options["verbosity"] = logging.ERROR

        if "max_retries" not in self.options:
            self.options["max_retries"] = 3

    def __crawl_single_page(self, url: str, callback_q: Queue):

        try:
            self.logger.debug(f"fetching page {url} ...")

            page, infos = get_page(url)

            self.lock.acquire()
            pure_url = extract_pure_url(url)
            if pure_url in self.fetched_urls and url in self.fetched_urls[pure_url]:
                logging.info(
                    f"page {url} not parsed because it has already been fetched")
                return
            elif pure_url in self.fetched_urls and url not in self.fetched_urls[pure_url]:
                for inf in self.fetched_urls[pure_url].values():
                    if inf == infos:
                        logging.info(
                            f"page {url} not parsed because parameters does not change the source code")
                        return
                self.fetched_urls[pure_url][url] = infos
            else:
                self.fetched_urls[pure_url] = {url: infos}

        except requests.RequestException as e:
            logging.warning(e)
            if not self.lock.locked():
                self.lock.acquire()
            if url not in self.error_urls:
                self.error_urls[url] = 0
            self.error_urls[url] += 1
            return
        finally:
            if self.lock.locked():
                self.lock.release()

        link_elements = [normalize_url(url, el.get("href")) for el in page.find_all(
            "a") if el.get("href") and len(el.get("href")) > 0]
        link_elements = set(
            [l for l in link_elements if l and in_scope(self.scope, l)])

        self.logger.info(f"found {len(link_elements)} links in page {url}")

        script_urls = [normalize_url(url, el.get("src")) for el in page.find_all(
            "script") if el.get("src") and len(el.get("src")) > 0]
        script_urls = set([url for url in script_urls if url and (not self.options["scan_all_scripts"] and in_scope(
            self.scope, url)) or self.options["scan_all_scripts"]])

        self.logger.info(
            f"found {len(script_urls)} scripts in {url}")

        for link in link_elements:
            self.lock.acquire()
            is_new_link = link not in self.urls_to_fetch.union(
                self.fetched_urls.keys())
            for urls in self.fetched_urls.values():
                if link in urls:
                    is_new_link = False
                    break
            self.lock.release()

            if is_new_link:
                callback_q.put(link)

                self.lock.acquire()
                self.urls_to_fetch.add(link)
                self.lock.release()

        for src in script_urls:

            self.logger.debug(f"fetching links for page {url}")
            found_links = set([link for link in get_links_in_script(src) if len(link) > 0 and in_scope(
                self.scope, link)])

            self.lock.acquire()
            new_links = [
                link for link in found_links if link not in set(self.fetched_urls.keys()).union(self.urls_to_fetch)]
            self.lock.release()

            self.logger.debug(
                f"found {len(new_links)} new links for scripts in {url}")

            for link in new_links:
                callback_q.put(link)

            self.lock.acquire()
            self.urls_to_fetch.update(new_links)
            self.lock.release()

            self.logger.debug(f"fetched page {url}")

    def crawl(self):
        t_count = self.options["threads"]
        queue = Queue()
        threads = []
        old_length = 0
        while len(threads) + len(self.urls_to_fetch) > 0:
            while len(self.urls_to_fetch) > 0 and t_count - len(threads) > 0:
                self.logger.debug(
                    f"remaining pages to fetch: {len(self.urls_to_fetch)}")

                url = self.urls_to_fetch.pop()
                if url in self.error_urls and self.error_urls[url] >= self.options["max_retries"]:
                    continue
                threads.append(
                    Thread(target=self.__crawl_single_page, args=(url, queue), daemon=True))
                threads[-1].start()

            threads = [t for t in threads if t.is_alive()]
            if len(threads) != old_length:
                self.logger.debug(f"current running threads: {len(threads)}")
                old_length = len(threads)

            while callable(self.on_url_found):
                try:
                    self.on_url_found(queue.get_nowait())
                except Empty:
                    break
                except Full:
                    break
