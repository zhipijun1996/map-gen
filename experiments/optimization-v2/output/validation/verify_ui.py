"""Check every cohort/seed preview and its four real data links over HTTP."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from threading import Thread

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parents[1]


class Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *_):
        pass


def main():
    results = json.loads((OUT / 'results.json').read_text())
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(Quiet, directory=str(OUT)))
    Thread(target=server.serve_forever, daemon=True).start()
    errors = []
    count = 0
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path='/usr/bin/chromium', headless=True,
                                        args=['--disable-dev-shm-usage'])
            page = browser.new_page(viewport={'width': 1440, 'height': 1080})
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.on('requestfailed', lambda request: errors.append(request.url))
            page.goto(f'http://127.0.0.1:{server.server_port}/comparison.html')
            for cohort, seeds in results['cohorts'].items():
                page.select_option('#cohort', cohort)
                assert page.locator('#seed option').count() == len(seeds)
                for seed in seeds:
                    page.select_option('#seed', str(seed))
                    expected = f'figures/{cohort}-{seed}.svg'
                    assert page.locator('#map').get_attribute('src') == expected
                    assert page.locator('#svg').get_attribute('href') == expected
                    page.wait_for_function('''label => {
                        const doc=document.querySelector('#map').contentDocument;
                        return doc && doc.documentElement.textContent.includes(label);
                    }''', arg=f'{cohort} / Seed {seed} |')
                    for variant in results['variants']:
                        href = page.locator('#' + variant).get_attribute('href')
                        assert href == f'{cohort}/{variant}/seed-{seed}/layout.json'
                        data = json.loads((OUT / href).read_text())
                        assert (data['cohort'], data['variant'], data['seed']) == (cohort, variant, seed)
                        assert (OUT / href).parent.joinpath(data['full_record']).is_file()
                    count += 1
            page.select_option('#cohort', 'validation')
            page.select_option('#seed', str(results['cohorts']['validation'][0]))
            page.wait_for_function('''() => document.querySelector('#map').contentDocument
                .documentElement.textContent.includes('validation / Seed 930001 |')''')
            page.screenshot(path=str(OUT / 'validation/ui-screen.png'), full_page=True)
            browser.close()
        assert not errors, errors
        receipt = dict(status='PASS', checked_seed_views=count,
                       checked_layout_links=count * len(results['variants']), errors=errors)
        (OUT / 'validation/ui-check.json').write_text(json.dumps(receipt, indent=2) + '\n')
        print(json.dumps(receipt))
    finally:
        server.shutdown()


if __name__ == '__main__':
    main()
