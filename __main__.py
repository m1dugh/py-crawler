import json
import sys
from argparse import ArgumentParser
from selenium import webdriver
from requests.exceptions import RequestException

from pycrawler import Crawler
from pycrawler.utils import get_robots_file_urls
from pycrawler.model import AppUrl


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

    url_group = parser.add_mutually_exclusive_group(required=True)
    url_group.add_argument(
        "--url", "-u", help="the url to crawl at", type=str)
    url_group.add_argument(
        "--urls", "-uL", help="a file containing line separated urls", type=str)

    parser.add_argument(
        "--scan-all-scripts", help="scan all scripts for in scope urls even out of scope scripts", default=True, type=bool)

    parser.add_argument("--threads", "-t", default=5,
                        help="the number of concurrent threads", type=int)

    parser.add_argument("-r", "--robots", action="store_true",
                        help="fetch robots.txt urls")
    
    parser.add_argument("-v", "--verbosity", type=int, default=4, choices=range(6), help="the level of verbosity starting from 1 debug to 5 critical")

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
    options["verbosity"] = args.verbosity * 10
    options["scan_out_of_scope_scripts"] = args.scan_all_scripts
    options["threads"] = args.threads

    scope = json.loads(open(args.scope).read())

    if args.url:
        urls = set([AppUrl(args.url)])
    elif args.urls:
        urls = set()
        for l in open(args.urls).readlines():
            urls.add(AppUrl(l))

    if args.robots:
        robots_urls = set()
        for url in urls:
            try:
                robots_urls.update(get_robots_file_urls(url))
            except RequestException:
                pass

        urls.update(robots_urls)

    return urls, scope, driver, options


if __name__ == "__main__":
    urls, scope, driver, options = parseArgs()

    crawler = Crawler(urls, scope, driver, print, **options)
    try:
        crawler.crawl()
    except Exception as e:
        print(e)
    except KeyboardInterrupt:
        pass
    finally:
        print("closing driver ...", file=sys.stderr)
        driver.close()
        sys.exit(0)
