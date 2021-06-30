# py-crawler
## A web crawler using python

------

## Installation

```shell
> git clone https://github.com/m1dugh/py-crawler
> python3 ./py-crawler/setup.py install
```

## Usage

### command-line tool
```shell
> python3 ./py-crawler -s scope.json --url https://www.google.com/
```

#### **scope format**:
```json
// scope.json
{
	"include":
	[
		"^https?:\/\/\\w+\\.google\\.com" // regex format
		// ...
	],
	"exclude":
	[
		"^https?:\/\/\\www\\.google\\.com"
	]
}
``` 

fetches every url matching `^https?:\/\/\\w+\\.google\\.com` regex excluding those matching patterns in `exclude`

_NB: Run help command for further informations about the tool_
```
> python3 <path_to_pycrawler_folder> -h
```

### python module
1. Install py-crawler as a module
```
> python3 -m pip install ./py-crawler
```

`python-file.py :`
```python
import json
from pycrawler import Crawler

def on_url_found(url):
	print(f"new url found by crawler: {url}")


with open("scope.json") as file:
	scope = json.loads(file.read())

base_urls = [
	"https://www.google.com/"
]

options = {
	"threads": 5
}

crawler = Crawler(base_urls, scope, on_url_found, threads=5, max_retries=2)

crawler.crawl()

print(crawler.fetched_urls)

```
