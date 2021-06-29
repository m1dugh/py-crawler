import re
import requests
import hashlib
from html import unescape
from requests.exceptions import RequestException
from bs4 import BeautifulSoup


pattern = re.compile(r"https?:\/\/([\w\-]+\.)+[a-z]{2,5}[^\s\"\']*")


def get_page(url: str) -> tuple[BeautifulSoup, tuple[int, int, str]]:
    res = requests.get(url)

    # returns BeautifulSoup and (status code, response length, response checksum)
    return BeautifulSoup(res.text, "html.parser"), (res.status_code, len(res.text), hashlib.sha256(res.text.encode('utf-8')).hexdigest())


def extract_root_url(url: str) -> str:
    match = re.match(r"https?:\/\/([\w\-]+\.)+[a-z]{2,5}", url)
    if match:
        return match.group(0)


def extract_pure_url(url: str) -> str:
    return url.split(sep="?")[0].split(sep="#")[0]


def normalize_url(page_url: str, found_url: str) -> str:
    root_url = extract_root_url(page_url)
    if not root_url or found_url.startswith("mailto:") or found_url.startswith("tel:"):
        return None
    if re.match(pattern, found_url):
        return unescape(found_url)
    elif found_url.startswith("/"):
        return unescape(root_url + found_url)
    elif found_url.startswith("#"):
        return unescape(page_url + found_url)
    else:
        return unescape(f"{page_url}/{found_url}")


def in_scope(scope, url):
    included = False
    try:
        for inc in scope["include"]:
            if re.compile(inc).match(url):
                included = True
                break
    except KeyError:
        return False
    if not included:
        return False

    try:
        for ex in scope["exclude"]:
            if re.compile(ex).match(url):
                return False
        return True
    except KeyError:
        return True


def get_links_in_script(url) -> str:
    try:
        response = requests.get(url)
        return [unescape(u.group(0)) for u in re.finditer(pattern, response.text)]
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
        return [f"{root_url}/{line}" for line in disallowed + allowed if not "*" in line]
    except RequestException:
        return []


def get_sitemap_file(path):
    response = requests.get(path)
    print(response.text)
