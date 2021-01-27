#!/usr/bin/env python

import argparse
import asyncio
import json
import logging

from crawler import url_crawler

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("url", type=str, help="Base URL")
    parser.add_argument("-n", type=int, default=10, help="Concurrency (default=10)")
    parser.add_argument("-d", type=int, default=1, help="Depth limit (default=1)")
    parser.add_argument("-o", type=str, default='./output.json', help="Output file (default=output.json)")
    args = parser.parse_args()

    graph = await url_crawler(args.url, args.d, args.n)

    with open(args.output_file, 'w') as f:
        f.write(json.dumps(graph, indent=4))

if __name__ == '__main__':
    asyncio.run(main())
