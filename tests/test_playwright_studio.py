"""Testes de navegação do estúdio. Não carregam o modelo de voz.

Preparação:
    npm --prefix frontend ci && npm --prefix frontend run build
    python -m pip install playwright
    python -m playwright install chromium
    python -m unittest discover -s tests -p 'test_playwright_*.py'
"""
import json
import re
from io import BytesIO
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
import unittest
import wave

try:
    from playwright.sync_api import sync_playwright, expect
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
            "/v1/projects": [{"id": "default", "name": "Projeto inicial"}],
            "/v1/characters": [],
        }
        for endpoint, response in responses.items():
            page.route(f"**{endpoint}*", lambda route, request, payload=response:
                       route.fulfill(status=200, content_type="application/json", body=json.dumps(payload)))
        page.goto(self.url, wait_until="networkidle")
        return page

    def mock_analysis(self, page, dialogue=False, saved_voice=False, second_character=False, scene_title=None):
        source_text = 'A noite chegou. "Olá!"' if dialogue else 'A noite chegou.'
        segments = [{"id": 0, "kind": "narration", "text": "A noite chegou.",
                     "speaker": "Narrador", "gender": "unknown", "delivery": "neutral"}]
        if dialogue:
            segments.append({"id": 1, "kind": "dialogue", "text": "Olá!", "speaker": "Lia",
                             "gender": "female", "delivery": "neutral",
                             "voice_id": "actor-1" if saved_voice else "",
                             "character_saved": saved_voice})
        if second_character:
            segments.append({"id": 2, "kind": "dialogue", "text": "Volte!", "speaker": "Bia",
                             "gender": "female", "delivery": "neutral", "voice_id": ""})
        job_response = {"id": "analysis-test", "status": "review", "stage": "review",
                        "completed": 0, "total": 0, "error": None, "source_text": source_text,
                        "analysis_percent": 100, "scene": {"method": "test", "warning": None, "segments": segments}}
        if scene_title is not None:
            job_response['scene']['title'] = scene_title
        approvals = []

        def approve(route):
            approvals.append(route.request.post_data_json)
            job_response.update(status="running", stage="loading")
            route.fulfill(status=202, content_type="application/json", body='{"id":"analysis-test"}')

        page.route("**/v1/jobs", lambda route: route.fulfill(
            status=202, content_type="application/json", body='{"id":"analysis-test"}'))
        page.route("**/v1/jobs/analysis-test", lambda route: route.fulfill(
            status=200, content_type="application/json", body=json.dumps(job_response)))
        page.route("**/v1/jobs/analysis-test/perform", approve)
        page.locator("#narration-text").fill(source_text)
        page.get_by_role("button", name="Analisar texto e escolher vozes").click()
        expect(page.get_by_role("heading", name="Confira as vozes da cena")).to_be_visible()
        return approvals

    def test_projeto_no_topo_adapta_e_permite_criar_em_todas_as_larguras(self):
        page = self.open_studio()
        try:
            for viewport_width in [360, 390, 768, 1024, 1440, 1920]:
                page.set_viewport_size({'width': viewport_width, 'height': 1000})
                expect(page.locator('header #studio-project')).to_be_visible()
                expect(page.locator('main #studio-project')).to_have_count(0)
                expect(page.get_by_text('Sua próxima narração', exact=True)).to_have_count(0)
                page.get_by_role('button', name='Novo projeto', exact=True).click()
                expect(page.locator('#new-project-name')).to_be_visible()
                expect(page.get_by_role('button', name='Criar projeto', exact=True)).to_be_visible()
                self.assertTrue(page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'))
                project_form = page.locator('.project-create-form').bounding_box()
                self.assertGreaterEqual(project_form['x'], 0)
                self.assertLessEqual(project_form['x'] + project_form['width'], viewport_width)
                page.get_by_role('button', name='Cancelar', exact=True).click()
                page.screenshot(path=f'/tmp/voxarcana-project-top-{viewport_width}.png', full_page=True)
        finally:
            page.close()

    def test_titulo_da_analise_aparece_e_preserva_edicao_manual_apos_reload(self):
        page = self.open_studio()
        try:
            self.mock_analysis(page, scene_title='A chegada da noite')
            expect(page.locator('#narration-title')).to_have_value('A chegada da noite')
            page.locator('#narration-title').fill('Título escolhido por mim')
            page.reload(wait_until='networkidle')
            expect(page.locator('#narration-title')).to_have_value('Título escolhido por mim')
        finally:
            page.close()

    def test_titulo_manual_durante_analise_nao_e_substituido_pela_sugestao(self):
        page = self.open_studio()
        job_response = {'id': 'title-test', 'status': 'running', 'stage': 'analyzing',
                        'completed': 0, 'total': 0, 'error': None, 'scene': None,
                        'source_text': 'A noite chegou.'}
        page.route('**/v1/jobs', lambda route: route.fulfill(status=202, json={'id': 'title-test'}))
        page.route('**/v1/jobs/title-test', lambda route: route.fulfill(json=job_response))
        try:
            page.locator('#narration-text').fill('A noite chegou.')
            page.get_by_role('button', name='Analisar texto e escolher vozes').click()
            expect(page.get_by_role('button', name='Cancelar', exact=True)).to_be_enabled()
            page.locator('#narration-title').fill('Título manual durante a análise')
            job_response.update(status='review', stage='review', scene={
                'title': 'Sugestão automática', 'method': 'test', 'warning': None,
                'segments': [{'id': 0, 'kind': 'narration', 'speaker': 'Narrador',
                              'text': 'A noite chegou.', 'gender': 'unknown', 'delivery': 'neutral'}]})
            expect(page.get_by_role('heading', name='Confira as vozes da cena')).to_be_visible()
            expect(page.locator('#narration-title')).to_have_value('Título manual durante a análise')
        finally:
            page.close()

    def test_narracao_so_gera_audio_apos_confirmacao(self):
        page = self.open_studio()
        try:
            generate_button = page.get_by_role("button", name="Gerar áudio", exact=True)
            expect(generate_button).to_be_disabled()
            approvals = self.mock_analysis(page)
            expect(generate_button).to_be_enabled()
            self.assertEqual(approvals, [])
            generate_button.click()
            expect(page.get_by_role("button", name="Gerando áudio…")).to_be_visible()
            self.assertEqual(len(approvals), 1)
            self.assertEqual(approvals[0]["lines"], [])
            self.assertEqual(approvals[0]["voice"], "narrator-1")
        finally:
            page.close()

    def test_configuracao_recolhivel_preserva_escolhas_e_permite_gerar(self):
        page = self.open_studio(voices=[
            {'id': 'narrator-1', 'name': 'Narrador', 'role': 'narrator'},
            {'id': 'actor-1', 'name': 'Atriz', 'role': 'character', 'gender': 'female'},
        ])
        try:
            self.mock_analysis(page, dialogue=True)
            page.locator('#actor-voice-0').select_option('actor-1')
            page.locator('#generation-speed').select_option('1.25')
            cast_heading = page.locator('.cast-review > summary')
            cast_heading.click()
            expect(page.locator('#actor-voice-0')).not_to_be_visible()
            expect(page.locator('#generation-speed')).to_be_visible()
            expect(page.get_by_role('button', name='Gerar áudio', exact=True)).to_be_enabled()
            cast_heading.focus()
            cast_heading.press('Enter')
            expect(page.locator('#actor-voice-0')).to_have_value('actor-1')
            expect(page.locator('#actor-voice-0')).to_be_visible()
            page.locator('.analysis-settings > summary').click()
            expect(page.locator('#actor-voice-0')).not_to_be_visible()
            expect(page.get_by_role('button', name='Gerar áudio', exact=True)).to_be_enabled()
            page.locator('.analysis-settings > summary').click()
            expect(page.locator('#actor-voice-0')).to_have_value('actor-1')
            expect(page.locator('#generation-speed')).to_have_value('1.25')
        finally:
            page.close()

    def test_projetos_separam_rascunhos_e_recuperam_projeto_apos_reload(self):
        page = self.open_studio()
        project_records = [{'id': 'default', 'name': 'Projeto inicial'}]

        def project_request(route):
            if route.request.method == 'POST':
                project_record = {'id': 'outro-projeto', 'name': route.request.post_data_json['name']}
                project_records.append(project_record)
                route.fulfill(status=201, json=project_record)
            else:
                route.fulfill(json=project_records)

        page.route('**/v1/projects', project_request)
        try:
            page.locator('#narration-title').fill('Primeira cena')
            page.locator('#narration-text').fill('Texto do projeto inicial.')
            page.get_by_role('button', name='Novo projeto', exact=True).click()
            page.locator('#new-project-name').fill('Outra campanha')
            page.get_by_role('button', name='Criar projeto', exact=True).click()
            expect(page.locator('#studio-project')).to_have_value('outro-projeto')
            expect(page.locator('#narration-text')).to_have_value('')
            page.locator('#narration-text').fill('Texto da outra campanha.')
            page.locator('#studio-project').select_option('default')
            expect(page.locator('#narration-text')).to_have_value('Texto do projeto inicial.')
            expect(page.locator('#narration-title')).to_have_value('Primeira cena')
            page.locator('#studio-project').select_option('outro-projeto')
            page.reload(wait_until='networkidle')
            expect(page.locator('#studio-project')).to_have_value('outro-projeto')
            expect(page.locator('#narration-text')).to_have_value('Texto da outra campanha.')
        finally:
            page.close()

    def test_geracao_direta_usa_narrador_sem_interpretacao_e_recupera_apos_reload(self):
        page = self.open_studio()
        requests = []

        def generate_narration(route):
            requests.append(route.request.post_data_json)
            route.fulfill(status=202, content_type="application/json", body='{"id":"narration-test"}')

        page.route("**/v1/jobs", generate_narration)
        page.route("**/v1/jobs/narration-test", lambda route: route.fulfill(
            status=200, content_type="application/json", body=json.dumps({
                "id": "narration-test", "status": "running", "stage": "queued",
                "completed": 1, "total": 3, "error": None, "scene": None})))
        try:
            narration_button = page.get_by_role("button", name="Gerar só com narrador", exact=True)
            expect(narration_button).to_be_disabled()
            source_text = 'A noite chegou. "Olá!" disse Lia.'
            page.locator("#narration-text").fill(source_text)
            for viewport_width in [390, 768, 1440]:
                page.set_viewport_size({"width": viewport_width, "height": 1000})
                self.assertTrue(page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"))
            narration_button.click()
            expect(page.get_by_role("button", name="Gerando áudio…", exact=True)).to_be_visible()
            self.assertEqual(len(requests), 1)
            self.assertEqual(requests[0]["text"], source_text)
            self.assertEqual(requests[0]["voice"], "narrator-1")
            self.assertIs(requests[0]["automatic"], False)
            self.assertIs(requests[0]["review"], False)
            expect(page.get_by_role("progressbar", name="Interpretação pela IA")).to_have_count(0)
            expect(page.get_by_role("button", name="Cancelar", exact=True)).to_be_enabled()
            page.reload(wait_until="networkidle")
            expect(page.get_by_role("button", name="Gerando áudio…", exact=True)).to_be_visible()
            expect(page.get_by_role("progressbar", name="Interpretação pela IA")).to_have_count(0)
            self.assertEqual(len(requests), 1)
        finally:
            page.close()

    def test_editar_durante_geracao_preserva_audio_e_rascunho_apos_reload(self):
        page = self.open_studio(voices=[
            {"id": "narrator-1", "name": "Narrador original", "role": "narrator"},
            {"id": "narrator-2", "name": "Outro narrador", "role": "narrator"},
        ])
        requests = []
        job_response = {"id": "editable-job", "status": "running", "stage": "synthesizing",
                        "completed": 0, "total": 2, "error": None, "scene": None}

        def start_narration(route):
            requests.append(route.request.post_data_json)
            route.fulfill(status=202, content_type="application/json", body='{"id":"editable-job"}')

        page.route("**/v1/jobs", start_narration)
        page.route("**/v1/jobs/editable-job", lambda route: route.fulfill(
            status=200, content_type="application/json", body=json.dumps(job_response)))
        audio_buffer = BytesIO()
        with wave.open(audio_buffer, 'wb') as audio_file:
            audio_file.setnchannels(1)
            audio_file.setsampwidth(2)
            audio_file.setframerate(24000)
            audio_file.writeframes(bytes(48000))
        page.route("**/v1/jobs/editable-job/audio", lambda route: route.fulfill(
            status=200, content_type="audio/wav", body=audio_buffer.getvalue()))
        try:
            page.locator('#narration-title').fill('Cena original')
            page.locator('#narration-text').fill('Texto original.')
            page.get_by_role('button', name='Gerar só com narrador', exact=True).click()
            expect(page.get_by_role('button', name='Gerando áudio…', exact=True)).to_be_visible()
            expect(page.get_by_role('button', name='Carregar exemplo')).to_be_enabled()
            page.locator('#narration-title').fill('Próxima cena')
            page.locator('#narration-text').fill('Texto para depois.')
            page.locator('#voice').select_option('narrator-2')
            page.locator('#generation-speed').select_option('1.25')
            page.locator('#acting').select_option('calm')
            expect(page.get_by_role('button', name='Gerando áudio…', exact=True)).to_be_disabled()
            expect(page.get_by_role('button', name='Cancelar', exact=True)).to_be_enabled()
            self.assertEqual(requests[0]['text'], 'Texto original.')
            self.assertEqual(requests[0]['voice'], 'narrator-1')
            self.assertEqual(requests[0]['speed'], 1)
            self.assertEqual(requests[0]['style'], 'neutral')
            page.reload(wait_until='networkidle')
            expect(page.locator('#narration-title')).to_have_value('Próxima cena')
            expect(page.locator('#narration-text')).to_have_value('Texto para depois.')
            expect(page.locator('#voice')).to_have_value('narrator-2')
            expect(page.locator('#generation-speed')).to_have_value('1.25')
            job_response.update(status='done', completed=2)
            expect(page.locator('.player-track strong')).to_have_text('Cena original')
            expect(page.get_by_role('button', name='Gerar só com narrador', exact=True)).to_be_enabled()
            self.assertEqual(len(requests), 1)
        finally:
            page.close()

    def test_edicao_do_elenco_durante_geracao_sobrevive_a_atualizacoes_de_progresso(self):
        page = self.open_studio(voices=[
            {'id': 'narrator-1', 'name': 'Narrador', 'role': 'narrator'},
            {'id': 'actor-1', 'name': 'Atriz', 'role': 'character', 'gender': 'female'},
        ])
        try:
            approvals = self.mock_analysis(page, dialogue=True, saved_voice=True)
            running_job = {'id': 'analysis-test', 'status': 'running', 'stage': 'synthesizing',
                           'completed': 0, 'total': 2, 'error': None,
                           'source_text': page.locator('#narration-text').input_value(),
                           'scene': {'method': 'test', 'warning': None, 'segments': [
                               {'id': 0, 'kind': 'narration', 'text': 'A noite chegou.',
                                'speaker': 'Narrador', 'gender': 'unknown', 'delivery': 'neutral'},
                               {'id': 1, 'kind': 'dialogue', 'text': 'Olá!', 'speaker': 'Lia',
                                'gender': 'female', 'delivery': 'neutral', 'voice_id': 'actor-1',
                                'character_saved': True},
                           ]}}
            page.route('**/v1/jobs/analysis-test', lambda route: route.fulfill(
                status=200, content_type='application/json', body=json.dumps(running_job)))
            page.get_by_role('button', name='Gerar áudio', exact=True).click()
            expect(page.get_by_role('button', name='Cancelar', exact=True)).to_be_enabled()
            page.locator('#actor-name-0').fill('Nome para próxima geração')
            for progress_update in range(2):
                page.wait_for_event('response', predicate=lambda response:
                                    response.url.endswith('/v1/jobs/analysis-test'))
                expect(page.locator('#actor-name-0')).to_have_value('Nome para próxima geração')
            self.assertEqual(len(approvals), 1)
            self.assertEqual(approvals[0]['lines'][0]['speaker'], 'Lia')
        finally:
            page.close()

    def test_personagem_exige_voz_e_texto_alterado_exige_nova_analise(self):
        page = self.open_studio(voices=[
            {"id": "narrator-1", "name": "Narrador", "role": "narrator", "gender": "neutral"},
            {"id": "actor-1", "name": "Atriz", "role": "character", "gender": "female"},
        ])
        try:
            approvals = self.mock_analysis(page, dialogue=True)
            generate_button = page.get_by_role("button", name="Gerar áudio", exact=True)
            expect(generate_button).to_be_disabled()
            page.locator("#actor-voice-0").select_option("actor-1")
            expect(generate_button).to_be_enabled()
            page.locator("#narration-text").fill("O texto foi alterado.")
            expect(generate_button).to_be_disabled()
            expect(page.get_by_text("O texto mudou. Clique em Analisar novamente.")).to_be_visible()
            self.assertEqual(approvals, [])
        finally:
            page.close()

    def test_vozes_usadas_ficam_ocultas_e_checkbox_permite_compartilhar(self):
        page = self.open_studio(voices=[
            {'id': 'narrator-1', 'name': 'Narrador', 'role': 'narrator', 'gender': 'neutral'},
            {'id': 'actor-1', 'name': 'Carla', 'role': 'character', 'gender': 'female'},
            {'id': 'actor-2', 'name': 'Sulamita', 'role': 'character', 'gender': 'female'},
            {'id': 'actor-3', 'name': 'Bruna', 'role': 'character', 'gender': 'female'},
        ])
        page.route('**/v1/characters?*', lambda route: route.fulfill(status=200,
            content_type='application/json', body=json.dumps([
                {'id': 'outra', 'name': 'Outra personagem', 'gender': 'female',
                 'voice_id': 'actor-3', 'aliases': [], 'available': True, 'voice_name': 'Bruna'}])))
        try:
            approvals = self.mock_analysis(page, dialogue=True, second_character=True)
            first_voice = page.locator('#actor-voice-0')
            second_voice = page.locator('#actor-voice-1')
            expect(first_voice.locator('option[value="actor-3"]')).to_have_count(0)
            first_voice.select_option('actor-1')
            expect(second_voice.locator('option[value="actor-1"]')).to_have_count(0)
            second_voice.select_option('actor-2')
            generate_button = page.get_by_role('button', name='Gerar áudio', exact=True)
            expect(generate_button).to_be_enabled()
            reuse_checkbox = page.get_by_role('checkbox', name='Usar voz já utilizada', exact=True)
            reuse_checkbox.check()
            expect(second_voice.locator('option[value="actor-1"]')).to_have_count(1)
            expect(second_voice.locator('option[value="actor-3"]')).to_have_count(1)
            second_voice.select_option('actor-1')
            expect(generate_button).to_be_enabled()
            reuse_checkbox.uncheck()
            expect(first_voice).to_have_value('actor-1')
            expect(second_voice).to_have_value('')
            expect(generate_button).to_be_disabled()
            reuse_checkbox.check()
            second_voice.select_option('actor-1')
            generate_button.click()
            self.assertEqual([line['voice_id'] for line in approvals[0]['lines']], ['actor-1', 'actor-1'])
        finally:
            page.close()

    def test_elenco_salva_apelidos_e_filtra_voz_de_outro_personagem(self):
        page = self.open_studio(voices=[
            {'id': 'narrator-1', 'name': 'Narrador', 'role': 'narrator'},
            {'id': 'actor-1', 'name': 'Leo', 'role': 'character'},
            {'id': 'actor-2', 'name': 'Carla', 'role': 'character'},
        ])
        characters = [
            {'id': 'lucasalmeida', 'name': 'Lucas Almeida', 'gender': 'male', 'voice_id': 'actor-1', 'aliases': [], 'voice_name': 'Leo', 'available': True},
            {'id': 'lia', 'name': 'Lia', 'gender': 'female', 'voice_id': 'actor-2', 'aliases': [], 'voice_name': 'Carla', 'available': True},
        ]
        edits = []
        page.route('**/v1/characters?*', lambda route: route.fulfill(status=200,
            content_type='application/json', body=json.dumps(characters)))

        def save_aliases(route):
            changes = route.request.post_data_json
            edits.append(changes)
            route.fulfill(status=200, content_type='application/json', body=json.dumps({**characters[0], **changes}))

        page.route('**/v1/characters/lucasalmeida?*', save_aliases)
        try:
            page.get_by_role('button', name='Elenco salvo · personagens e vozes').click()
            page.locator('#saved-character').select_option('lucasalmeida')
            expect(page.locator('#saved-character-voice option[value="actor-2"]')).to_have_count(0)
            page.get_by_role('checkbox', name='Usar voz já utilizada', exact=True).check()
            expect(page.locator('#saved-character-voice option[value="actor-2"]')).to_have_count(1)
            page.locator('#saved-character-aliases').fill('Almeida, Corvo')
            page.get_by_role('button', name='Salvar personagem', exact=True).click()
            expect(page.get_by_text('Personagem salvo. Analise novamente o texto para aplicar os vínculos à cena.')).to_be_visible()
            self.assertEqual(edits[0]['aliases'], ['Almeida', 'Corvo'])
            self.assertEqual(edits[0]['voice_id'], 'actor-1')
        finally:
            page.close()

    def test_adiciona_personagem_salvo_remove_da_cena_e_preserva_falas(self):
        page = self.open_studio(voices=[
            {'id': 'narrator-1', 'name': 'Narrador', 'role': 'narrator', 'gender': 'neutral'},
            {'id': 'actor-1', 'name': 'Carla', 'role': 'character', 'gender': 'female'},
            {'id': 'actor-2', 'name': 'Leo', 'role': 'character', 'gender': 'male'},
        ])
        saved_character = {'id': 'garrin', 'name': 'Garrin', 'gender': 'male', 'voice_id': 'actor-2',
                           'aliases': ['Ferreiro'], 'voice_name': 'Leo', 'available': True}
        page.route('**/v1/characters?*', lambda route: route.fulfill(status=200,
            content_type='application/json', body=json.dumps([saved_character])))
        character_mutations = []
        page.on('request', lambda request: character_mutations.append(request.url)
                if '/v1/characters' in request.url and request.method != 'GET' else None)
        try:
            approvals = self.mock_analysis(page, dialogue=True)
            page.locator('#actor-voice-0').select_option('actor-1')
            generate_button = page.get_by_role('button', name='Gerar áudio', exact=True)
            expect(generate_button).to_be_enabled()
            saved_picker = page.locator('#scene-saved-character')
            saved_picker.select_option('garrin')
            page.get_by_role('button', name='Adicionar à cena', exact=True).click()
            expect(page.locator('#actor-name-1')).to_have_value('Garrin')
            expect(page.locator('#actor-gender-1')).to_have_value('male')
            expect(page.locator('#actor-voice-1')).to_have_value('actor-2')
            expect(saved_picker.locator('option[value="garrin"]')).to_have_count(0)
            page.get_by_role('button', name='Remover Garrin da cena', exact=True).click()
            expect(page.locator('.actor-row')).to_have_count(1)
            expect(generate_button).to_be_enabled()
            expect(saved_picker.locator('option[value="garrin"]')).to_have_count(1)
            saved_picker.select_option('garrin')
            page.get_by_role('button', name='Adicionar à cena', exact=True).click()
            page.get_by_role('button', name='Remover Lia da cena', exact=True).click()
            expect(page.locator('.actor-row')).to_have_count(1)
            expect(page.locator('.review-lines')).to_have_attribute('open', '')
            expect(page.get_by_text('1 fala sem personagem. Escolha quem fala antes de gerar o áudio.')).to_be_visible()
            expect(generate_button).to_be_disabled()
            expect(page.locator('#line-speaker-1')).to_have_value('')
            expect(page.locator('.review-line p')).to_have_text('Olá!')
            page.locator('#line-speaker-1').select_option(label='Garrin')
            expect(generate_button).to_be_enabled()
            generate_button.click()
            self.assertEqual(approvals[0]['lines'], [{'id': 1, 'speaker': 'Garrin', 'gender': 'male', 'voice_id': 'actor-2'}])
            self.assertEqual(character_mutations, [])
        finally:
            page.close()

    def test_remove_ultimo_personagem_e_permite_criar_substituto(self):
        page = self.open_studio(voices=[
            {'id': 'narrator-1', 'name': 'Narrador', 'role': 'narrator', 'gender': 'neutral'},
            {'id': 'actor-1', 'name': 'Carla', 'role': 'character', 'gender': 'female'},
        ])
        try:
            self.mock_analysis(page, dialogue=True)
            page.get_by_role('button', name='Remover Lia da cena', exact=True).click()
            expect(page.locator('.actor-row')).to_have_count(0)
            expect(page.get_by_role('button', name='Gerar áudio', exact=True)).to_be_disabled()
            expect(page.get_by_text('Adicione um personagem e atribua as falas abaixo.')).to_be_visible()
            page.get_by_role('button', name='Novo personagem', exact=True).click()
            page.locator('#actor-name-0').fill('Brigitte')
            page.locator('#actor-voice-0').select_option('actor-1')
            page.locator('#line-speaker-1').select_option(label='Brigitte')
            expect(page.get_by_role('button', name='Gerar áudio', exact=True)).to_be_enabled()
            for viewport_width in [390, 768, 1440]:
                page.set_viewport_size({'width': viewport_width, 'height': 1000})
                self.assertTrue(page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'))
                page.screenshot(path=f'/tmp/voxarcana-cast-edit-{viewport_width}.png', full_page=True)
        finally:
            page.close()

    def test_troca_narrador_e_gera_novamente_sem_reanalisar_nem_perder_correcao(self):
        page = self.open_studio(voices=[
            {'id': 'narrator-1', 'name': 'Narrador anterior', 'role': 'narrator', 'gender': 'male'},
            {'id': 'narrator-2', 'name': 'Narrador correto', 'role': 'narrator', 'gender': 'male'},
            {'id': 'actor-1', 'name': 'Carla', 'role': 'character', 'gender': 'female'},
        ])
        analysis_requests = []
        page.on('request', lambda request: analysis_requests.append(request.url)
                if request.url.endswith('/v1/jobs') and request.method == 'POST' else None)
        audio_buffer = BytesIO()
        with wave.open(audio_buffer, 'wb') as recording:
            recording.setnchannels(1)
            recording.setsampwidth(2)
            recording.setframerate(24000)
            recording.writeframes(b'\x00\x01' * 24000)
        try:
            approvals = self.mock_analysis(page, dialogue=True, saved_voice=True)
            page.locator('#actor-name-0').fill('Lise')
            completed_job = {'id': 'analysis-test', 'status': 'done', 'completed': 2, 'total': 2,
                'error': None, 'source_text': 'A noite chegou. "Olá!"', 'analysis_percent': 100,
                'scene': {'method': 'test', 'warning': None, 'segments': [
                    {'id': 0, 'kind': 'narration', 'text': 'A noite chegou.', 'speaker': 'Narrador', 'gender': 'unknown', 'delivery': 'neutral'},
                    {'id': 1, 'kind': 'dialogue', 'text': 'Olá!', 'speaker': 'Lise', 'gender': 'female', 'delivery': 'neutral', 'voice_id': 'actor-1'}]}}
            page.route('**/v1/jobs/analysis-test', lambda route: route.fulfill(
                status=200, content_type='application/json', body=json.dumps(completed_job)))
            page.route('**/v1/jobs/analysis-test/audio', lambda route: route.fulfill(
                status=200, content_type='audio/wav', body=audio_buffer.getvalue()))
            generate_button = page.get_by_role('button', name='Gerar áudio', exact=True)
            generate_button.click()
            expect(page.get_by_role('button', name='Reproduzir narração', exact=True)).to_be_enabled()
            expect(page.locator('#actor-name-0')).to_have_value('Lise')
            page.locator('#voice').select_option('narrator-2')
            expect(generate_button).to_be_enabled()
            expect(page.locator('#actor-voice-0')).to_have_value('actor-1')
            generate_button.click()
            expect(generate_button).to_be_enabled()
            self.assertEqual(len(analysis_requests), 1)
            self.assertEqual(len(approvals), 2)
            self.assertEqual(approvals[0]['voice'], 'narrator-1')
            self.assertEqual(approvals[1]['voice'], 'narrator-2')
            self.assertEqual(approvals[0]['lines'], approvals[1]['lines'])
            self.assertEqual(approvals[1]['lines'][0]['speaker'], 'Lise')
            page.reload(wait_until='networkidle')
            expect(page.locator('#actor-name-0')).to_have_value('Lise')
            expect(generate_button).to_be_enabled()
            page.locator('#narration-text').fill('Outro texto.')
            expect(generate_button).to_be_disabled()
            expect(page.get_by_text('O texto mudou. Clique em Analisar novamente.')).to_be_visible()
        finally:
            page.close()

    def test_elenco_salvo_aguarda_confirmacao_e_layout_adapta(self):
        page = self.open_studio(voices=[
            {"id": "narrator-1", "name": "Narrador", "role": "narrator", "gender": "neutral"},
            {"id": "actor-1", "name": "Atriz", "role": "character", "gender": "female"},
        ])
        try:
            approvals = self.mock_analysis(page, dialogue=True, saved_voice=True)
            generate_button = page.get_by_role("button", name="Gerar áudio", exact=True)
            expect(generate_button).to_be_enabled()
            self.assertEqual(page.locator("#actor-voice-0").input_value(), "actor-1")
            page.locator('.scene-preview > summary').click()
            expect(page.get_by_role('list', name='Trechos da cena interpretada')).to_be_visible()
            for viewport_width in [390, 768, 1024, 1440, 1920]:
                page.set_viewport_size({"width": viewport_width, "height": 1000})
                self.assertTrue(page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"))
                action_buttons = page.locator('.generation-options > button')
                self.assertEqual(action_buttons.count(), 3)
                button_positions = [action_buttons.nth(button_index).bounding_box() for button_index in range(3)]
                self.assertAlmostEqual(button_positions[0]['y'], button_positions[1]['y'], delta=1)
                self.assertAlmostEqual(button_positions[1]['y'], button_positions[2]['y'], delta=1)
                self.assertLess(button_positions[0]['x'], button_positions[1]['x'])
                self.assertLess(button_positions[1]['x'], button_positions[2]['x'])
                progress_phases = page.locator('.progress-phase')
                if viewport_width >= 768:
                    self.assertAlmostEqual(progress_phases.nth(0).bounding_box()['y'], progress_phases.nth(1).bounding_box()['y'], delta=1)
                page.screenshot(path=f"/tmp/voxarcana-steps-{viewport_width}.png", full_page=True)
            self.assertEqual(approvals, [])
            generate_button.click()
            expect(page.get_by_role("button", name="Gerando áudio…")).to_be_visible()
            self.assertEqual(approvals[0]["lines"][0]["voice_id"], "actor-1")
        finally:
            page.close()

    def test_editor_exemplo_habilita_analise(self):
        page = self.open_studio()
        try:
            page.get_by_role("button", name="Carregar exemplo").click()
            self.assertIn("biblioteca", page.locator("#narration-text").input_value().lower())
            self.assertTrue(page.get_by_role("button", name="Analisar texto e escolher vozes").is_enabled())
            self.assertEqual(page.locator("#voice").input_value(), "narrator-1")
        finally:
            page.close()

    def test_youtube_recorta_baixa_e_importa_referencia_sem_gerar_narracao(self):
        page = self.open_studio()
        clip_requests = []
        voice_uploads = []
        narration_requests = []
        audio_buffer = BytesIO()
        with wave.open(audio_buffer, 'wb') as recording:
            recording.setnchannels(1)
            recording.setsampwidth(2)
            recording.setframerate(24000)
            recording.writeframes(b'\x00\x01' * (24000 * 30))
        wav = audio_buffer.getvalue()

        def extract_clip(route):
            clip_requests.append(route.request.post_data_json)
            route.fulfill(status=200, content_type='audio/wav', body=wav)

        def save_voice(route):
            voice_uploads.append(route.request.post_data_buffer)
            route.fulfill(status=200, content_type='application/json', body=json.dumps({
                'id': 'youtube-voice', 'name': 'Voz do trecho', 'role': 'both',
                'gender': 'unknown', 'kind': 'human', 'editable': True}))

        page.route('**/v1/audio/youtube', extract_clip)
        page.route('**/v1/voices/reference', save_voice)
        page.on('request', lambda request: narration_requests.append(request.url)
                if '/v1/jobs' in request.url else None)
        try:
            page.get_by_role('button', name='Adicionar voz de referência', exact=True).click()
            page.locator('#youtube-video-url').fill('https://youtu.be/BaW_jenozKc')
            page.locator('#youtube-clip-start').fill('01:99')
            page.get_by_role('button', name='Extrair 30 segundos', exact=True).click()
            expect(page.get_by_text('Informe o início em segundos, mm:ss ou hh:mm:ss, até 24 horas.')).to_be_visible()
            self.assertEqual(clip_requests, [])
            page.locator('#youtube-clip-start').fill('01:20')
            page.get_by_role('button', name='Extrair 30 segundos', exact=True).click()
            download_link = page.get_by_role('link', name='Baixar áudio de 30 segundos')
            expect(download_link).to_be_visible()
            self.assertEqual(clip_requests, [{'url': 'https://youtu.be/BaW_jenozKc', 'start_seconds': 80}])
            self.assertTrue(page.locator('audio[aria-label="Ouvir trecho extraído do YouTube"]').get_attribute('src').startswith('blob:'))
            with page.expect_download() as download_info:
                download_link.click()
            self.assertEqual(download_info.value.suggested_filename, 'youtube-80s-30s.wav')
            for viewport_width in [390, 768, 1440]:
                page.set_viewport_size({'width': viewport_width, 'height': 1000})
                self.assertTrue(page.locator('.reference-dialog[open]').evaluate(
                    'dialog => dialog.scrollWidth <= dialog.clientWidth'))
                if viewport_width >= 768:
                    profile_bounds = page.locator('.voice-profile').bounding_box()
                    source_bounds = page.locator('.voice-source').bounding_box()
                    self.assertLess(profile_bounds['x'], source_bounds['x'])
                    self.assertAlmostEqual(profile_bounds['y'], source_bounds['y'], delta=1)
                    self.assertTrue(page.locator('.voice-import-dialog').evaluate(
                        'dialog => dialog.scrollHeight <= dialog.clientHeight'))
                page.screenshot(path=f'/tmp/voxarcana-youtube-{viewport_width}.png', full_page=True)
            page.locator('#reference-name').fill('Voz do trecho')
            page.get_by_role('button', name='Adicionar voz', exact=True).click()
            expect(page.get_by_role('dialog')).not_to_be_visible()
            self.assertEqual(len(voice_uploads), 1)
            self.assertIn(b'youtube-80s-30s.wav', voice_uploads[0])
            self.assertIn(wav, voice_uploads[0])
            self.assertEqual(page.locator('#voice').input_value(), 'youtube-voice')
            self.assertEqual(narration_requests, [])
        finally:
            page.close()

    def test_falha_do_youtube_mantem_dialogo_disponivel(self):
        page = self.open_studio()
        page.route('**/v1/audio/youtube', lambda route: route.fulfill(
            status=422, content_type='application/json', body='{"detail":"Vídeo indisponível."}'))
        try:
            page.get_by_role('button', name='Adicionar voz de referência', exact=True).click()
            page.locator('#youtube-video-url').fill('https://youtu.be/BaW_jenozKc')
            page.get_by_role('button', name='Extrair 30 segundos', exact=True).click()
            expect(page.get_by_text('Vídeo indisponível.')).to_be_visible()
            expect(page.get_by_role('button', name='Extrair 30 segundos', exact=True)).to_be_enabled()
            expect(page.locator('#reference-file')).to_be_enabled()
            expect(page.get_by_role('button', name='Fechar', exact=True)).to_be_enabled()
        finally:
            page.close()

    def test_player_no_topo_permanece_visivel_e_controla_volume_do_audio(self):
        page = self.open_studio()
        audio_buffer = BytesIO()
        with wave.open(audio_buffer, 'wb') as recording:
            recording.setnchannels(1)
            recording.setsampwidth(2)
            recording.setframerate(24000)
            recording.writeframes(b'\x00\x01' * (24000 * 8))
        page.route('**/v1/jobs', lambda route: route.fulfill(
            status=202, content_type='application/json', body='{"id":"player-test"}'))
        page.route('**/v1/jobs/player-test', lambda route: route.fulfill(
            status=200, content_type='application/json', body=json.dumps({
                'id': 'player-test', 'status': 'done', 'completed': 1, 'total': 1,
                'error': None, 'scene': None})))
        page.route('**/v1/jobs/player-test/audio', lambda route: route.fulfill(
            status=200, content_type='audio/wav', body=audio_buffer.getvalue()))
        try:
            player = page.get_by_role('region', name='Reprodução da narração')
            expect(player).to_have_count(1)
            expect(page.locator('header .player')).to_be_visible()
            volume_slider = page.get_by_role('slider', name='Volume da reprodução')
            volume_slider.evaluate("slider => { slider.value = '0.35'; slider.dispatchEvent(new Event('input', { bubbles: true })); }")
            page.locator('#narration-text').fill('Uma narração para testar o player.')
            page.get_by_role('button', name='Gerar só com narrador', exact=True).click()
            narration_audio = page.locator('header audio')
            expect(narration_audio).to_have_attribute('src', re.compile('^blob:'))
            page.wait_for_function("document.querySelector('header audio')?.readyState >= 1")
            self.assertAlmostEqual(narration_audio.evaluate('audio => audio.volume'), .35)
            volume_slider.focus()
            volume_slider.press('ArrowRight')
            self.assertAlmostEqual(narration_audio.evaluate('audio => audio.volume'), .36)
            page.get_by_role('button', name='Silenciar áudio', exact=True).click()
            self.assertEqual(narration_audio.evaluate('audio => audio.volume'), 0)
            page.get_by_role('button', name='Ativar som', exact=True).click()
            self.assertAlmostEqual(narration_audio.evaluate('audio => audio.volume'), .36)
            page.get_by_role('button', name='Reproduzir narração', exact=True).click()
            expect(page.get_by_role('button', name='Pausar narração', exact=True)).to_be_visible()
            page.get_by_role('button', name='Pausar narração', exact=True).click()
            expect(page.get_by_role('button', name='Reproduzir narração', exact=True)).to_be_visible()
            page.locator('#narration-text').evaluate("editor => editor.style.minHeight = '1200px'")
            for viewport_width in [320, 390, 768, 1024, 1440, 1920]:
                page.set_viewport_size({'width': viewport_width, 'height': 900})
                page.evaluate('window.scrollTo(0, 500)')
                self.assertGreater(page.evaluate('window.scrollY'), 0)
                self.assertAlmostEqual(page.locator('header').bounding_box()['y'], 0, delta=1)
                self.assertTrue(page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'))
                expect(volume_slider).to_be_in_viewport()
                expect(page.get_by_role('button', name='Reproduzir narração', exact=True)).to_be_in_viewport()
                page.screenshot(path=f'/tmp/voxarcana-top-player-{viewport_width}.png')
            page.get_by_role('button', name='Parar reprodução', exact=True).click()
            self.assertEqual(narration_audio.evaluate('audio => audio.currentTime'), 0)
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
