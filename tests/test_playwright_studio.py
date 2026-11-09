"""Testes de navegação do estúdio. Não carregam o modelo de voz.

Preparação:
    npm --prefix frontend ci && npm --prefix frontend run build
    python -m pip install playwright
    python -m playwright install chromium
    python -m unittest discover -s tests -p 'test_playwright_*.py'
"""
import json
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
import unittest

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "frontend" / "dist"


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


@unittest.skipIf(sync_playwright is None, "Instale playwright para executar os testes do navegador")
class StudioBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (DIST / "index.html").exists():
            raise unittest.SkipTest("Compile o frontend com npm --prefix frontend run build")
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(DIST)))
        cls.thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        try:
            cls.playwright = sync_playwright().start()
            cls.browser = cls.playwright.chromium.launch()
        except Exception as error:
            cls.server.shutdown()
            if hasattr(cls, "playwright"):
                cls.playwright.stop()
            raise unittest.SkipTest(f"Instale o navegador Chromium do Playwright: {error}")
        cls.url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=3)

    def open_studio(self, voices=None):
        page = self.browser.new_page()
        voice_items = [{"id": "narrator-1", "name": "Narrador de teste", "role": "narrator", "gender": "neutral"}] if voices is None else voices
        responses = {
            "/v1/engine": {"id": "chatterbox-br", "name": "Chatterbox BR", "installed": True,
                           "reference_audio": True, "voice_description": False, "locale": "pt-BR"},
            "/v1/voices": voice_items,
            "/v1/styles": [{"id": "neutral", "name": "Neutro"}],
        }
        for endpoint, response in responses.items():
            page.route(f"**{endpoint}", lambda route, payload=response:
                       route.fulfill(status=200, content_type="application/json", body=json.dumps(payload)))
        page.goto(self.url, wait_until="networkidle")
        return page

    def test_editor_exemplo_habilita_analise(self):
        page = self.open_studio()
        try:
            page.get_by_role("button", name="Carregar exemplo").click()
            self.assertIn("biblioteca", page.locator("#narration-text").input_value().lower())
            self.assertTrue(page.get_by_role("button", name="Analisar texto e escolher vozes").is_enabled())
            self.assertEqual(page.locator("#voice").input_value(), "narrator-1")
        finally:
            page.close()

    def test_sem_voz_nao_inicia_analise(self):
        page = self.open_studio(voices=[])
        try:
            page.locator("#narration-text").fill("A cena de teste.")
            self.assertTrue(page.get_by_role("button", name="Analisar texto e escolher vozes").is_disabled())
            self.assertIn("Adicione uma voz", page.locator("#voice").inner_text())
        finally:
            page.close()

    def test_ajuda_mostra_instrucoes(self):
        page = self.open_studio()
        try:
            page.locator("button[aria-label='Como funciona']").click()
            self.assertTrue(page.get_by_text("Da sua imaginação para a mesa.").is_visible())
        finally:
            page.close()


if __name__ == "__main__":
    unittest.main()
