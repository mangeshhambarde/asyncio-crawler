import asyncio
import logging
from typing import Optional, Awaitable
from urllib.parse import urlparse

import aiohttp
from bs4 import BeautifulSoup
from url_normalize import url_normalize

logger = logging.getLogger(__name__)


async def download(url: str) -> Optional[str]:
    """
    Return HTML given a URL.
    """
    html = None
    try:
        async with aiohttp.ClientSession(trust_env=True) as session:
            async with session.get(url) as response:
                # only allow 200 and text/html
                if response.status == 200 and response.content_type == 'text/html':
                    html = await response.text()
    except (aiohttp.ClientError, UnicodeError):
        logger.info(f'500 {url}')
        return None
    else:
        logger.info(f'{response.status} {url}')
        return html


async def fetch_child_urls(url: str, depth: int) -> Optional[dict]:
    """
    Return child URLs given a URL.
    """
    # normalize and parse.
    url = url_normalize(url)
    url_obj = urlparse(url)

    result = {'depth': depth, 'url': url, 'children': set()}

    html = await download(url)
    if html is None:
        # if download fails, return empty children set.
        return result

    # get all <a> tags.
    for tag in BeautifulSoup(html, features='html.parser').find_all('a'):
        link = tag.get('href')
        if link is None:
            continue
        link = urlparse(link)
        if link.scheme == '':
            # relative links: append them to the parent's domain.
            tmp_url = f'{url_obj.scheme}://{url_obj.netloc}'
            tmp_url += link.path if link.path.startswith('/') else f'/{link.path}'
            if link.query != '': # parameters
                tmp_url += f'?{link.query}'
            result['children'].add(tmp_url)
        elif link.netloc != url_obj.netloc:
            # skip different domains
            continue
        elif link.scheme in ['http', 'https']:
            # only allow HTTP or HTTPS schemes.
            result['children'].add(url_normalize(link.geturl()))

    return result


async def url_crawler(base_url: str,
                      depth_limit: Optional[int] = 2,
                      concurrency: int = 10) -> dict:
    """
    Crawl a given URL and return a graph in form of an adjacency list.
    Crawl depth and concurrency can be specified.
    """
    # final graph to return.
    graph = {}

    # semaphore for concurrency.
    sem = asyncio.Semaphore(concurrency)

    # wrapper for enforcing concurrency using a provided semaphore.
    async def run_with_semaphore(sem: asyncio.Semaphore, task: Awaitable):
        async with sem:
            return await task

    # set of pending tasks (asyncio.Task)
    pending_tasks = set()

    # start crawling base URL with depth=0
    pending_tasks.add(asyncio.create_task(run_with_semaphore(sem, fetch_child_urls(base_url, 0))))

    while len(pending_tasks) > 0:

        # wait for a task to finish.
        done_tasks, pending_tasks = await asyncio.wait(
            pending_tasks, return_when=asyncio.FIRST_COMPLETED)

        # process done tasks.
        for task in done_tasks:
            task_result = task.result()

            # add parent to graph (also mark as seen)
            # change set->list to allow JSON serialization.
            graph[task_result['url']] = list(task_result['children'])

            # process child URLs if:
            # - not already seen (to avoid cycles)
            # - not reached depth limit
            for url in task_result['children']:
                if url not in graph and task_result['depth'] < depth_limit:
                    task = asyncio.create_task(run_with_semaphore(sem, fetch_child_urls(url, task_result['depth']+1)))
                    pending_tasks.add(task)
                    graph[url] = []  # mark seen

    return graph
