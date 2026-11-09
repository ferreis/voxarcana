# VoxArcana Studio

Estúdio local de narração para RPG. Usa Vue 3 no frontend, FastAPI no backend e Chatterbox PT-BR para gerar áudio WAV. A extensão Chromium continua disponível para leitura de texto.

## Instalação e inicialização

Na raiz do projeto, execute:

```bash
./start
```

O inicializador prepara o ambiente Python isolado em `backend/.venv-br`, instala dependências, baixa os modelos fixados no projeto, compila a interface e inicia o servidor local. A primeira execução exige internet e espaço para os modelos.

**Requisitos:** Node.js 20.19+ (linha 20) ou 22.12+, npm, FFmpeg (com `ffprobe`) e Python 3.10 a 3.12. Se não houver Python compatível, o script usa o gerenciador `uv` para instalar Python 3.12 dentro do projeto. `curl` ou `wget` são necessários nesse caso. Use `PYTHON_BIN=/caminho/python3.12 ./start` para selecionar um interpretador.

Abra **http://127.0.0.1:8765**. Encerre com **Ctrl+C**. O servidor não deve ser exposto à internet ou à rede local.

Com `VOXARCANA_DEVICE=auto` em `backend/.env`, o modelo de voz tenta usar a GPU. Se faltar memória durante o carregamento, continua na CPU, com geração mais lenta. Para tentar a GPU novamente após liberar memória, reinicie o backend. Use `VOXARCANA_DEVICE=cpu` para sempre usar a CPU; ao definir `cuda` explicitamente, a falta de memória é informada como erro.

O processamento de diálogos por inteligência artificial requer o **Ollama** instalado localmente e o modelo `qwen3:4b-instruct-2507-q4_K_M`. O backend usa a porta de loopback `11435` e pode preparar o modelo na primeira análise. Instalação do Ollama: https://ollama.com/download . Sem o Ollama, a análise pode recorrer à segmentação conservadora do texto.

Para reiniciar os serviços locais e o analisador Ollama usando o script de desenvolvimento, execute `./reiniciar.sh` depois de configurar o ambiente.

## Narração e biblioteca

1. Adicione uma gravação brasileira autorizada à biblioteca de vozes. O estúdio só usa referências importadas e registradas pelo usuário.
2. Cole uma cena de até 10.000 caracteres e escolha uma voz de narrador.
3. Clique em **Analisar texto e escolher vozes**. Confira os personagens detectados, as vozes e as falas.
4. Na etapa **2 · Gerar áudio**, confirme as vozes com o botão **Gerar áudio**. Use o player para ouvir ou baixar o WAV.

A análise sempre aguarda essa confirmação, inclusive em cenas com apenas narrador ou com personagens já salvos. Se alterar o texto, analise novamente antes de gerar.

A biblioteca permite classificar vozes como narrador, personagem ou ambos. O elenco pode memorizar escolhas para cenas futuras. Há controle de velocidade do arquivo exportado e nivelamento de volume por trecho. O ajuste de velocidade e a normalização dependem do FFmpeg.

Em **Adicionar voz**, também é possível colar um link de vídeo público do YouTube e informar o início em segundos, `mm:ss` ou `hh:mm:ss`. Clique em **Extrair 30 segundos** para ouvir o trecho, baixar somente o áudio WAV ou adicioná-lo à biblioteca com um nome e classificação. Escolha uma fala limpa e autorizada, sem música ou outras vozes. A extração usa internet, `yt-dlp` e FFmpeg no backend local; não usa o analisador de texto nem o modelo de voz. Vídeos privados, transmissões ao vivo e vídeos que exigem login não são suportados. O trecho precisa ter os 30 segundos completos disponíveis. Reinicie com `./start` após atualizar para instalar a dependência. Mudanças ou bloqueios do YouTube podem exigir atualizar `yt-dlp[default]` no ambiente Python.

Os trabalhos ficam temporariamente na memória do servidor. O rascunho, as preferências e o identificador do trabalho ficam no armazenamento local do navegador. O histórico de áudio não sobrevive ao reinício do backend.

## Extensão Chromium

Carregue o diretório `extension/` em `chrome://extensions` com o **Modo do desenvolvedor** ativo. A extensão permite usar vozes do Chrome ou o motor local, sempre mediante ação do usuário.

## Desenvolvimento e testes

```bash
npm --prefix frontend ci
npm --prefix frontend run build
node --test tests/extension.test.cjs
backend/.venv-br/bin/python -m unittest discover -s tests -p 'test_*.py'
```

Os testes de interface usam Playwright para Python e o frontend compilado:

```bash
python -m pip install playwright
python -m playwright install chromium
npm --prefix frontend run build
python -m unittest tests/test_playwright_studio.py
```

As verificações de API podem exigir `httpx`. O modelo de voz não é necessário para os testes de interface, que simulam respostas HTTP.

## Segurança e arquivos locais

O servidor utiliza `127.0.0.1`, não possui autenticação para acesso público e **não deve receber tráfego externo**. O frontend exige que o usuário escolha e envie referências de voz autorizadas. Modelos e gravações são armazenados em `backend/models/` e `backend/voices/`, ignorados pelo Git.

Documentação: [Arquitetura](docs/ARCHITECTURE.md), [Roadmap](docs/ROADMAP.md) e [Licenças de terceiros](docs/THIRD_PARTY.md).
