# SPDX-License-Identifier: Apache-2.0
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import threading

import pytest
from playwright.sync_api import sync_playwright

OUTPUT = Path(__file__).resolve().parents[2] / 'artifacts/docs-comparison'


@pytest.fixture(scope='session')
def output():
    return OUTPUT


@pytest.fixture(scope='session')
def server():
    handler = partial(SimpleHTTPRequestHandler, directory=str(OUTPUT))
    httpd = ThreadingHTTPServer(('127.0.0.1', 0), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f'http://127.0.0.1:{httpd.server_port}'
    httpd.shutdown()
    httpd.server_close()
    thread.join()


@pytest.fixture(scope='session')
def browser():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=os.environ.get('DOCS_BROWSER_EXECUTABLE'))
        yield browser
        browser.close()


@pytest.fixture(params=['sphinx', 'zensical'])
def variant(request):
    return request.param
