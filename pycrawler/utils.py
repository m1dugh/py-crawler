import re
import requests
from requests.exceptions import RequestException

from .model import AppUrl

pattern = re.compile(r"https?:\/\/([\w\-]+\.)+[a-z]{2,5}[^\s\"\']*")

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
