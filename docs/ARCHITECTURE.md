# Arquitetura do VoxArcana

## Fluxo da extensão

```text
Caixa de texto no popup / seleção pelo menu de contexto
                          |
                          v
              Service worker (background.js)
                          |
              +-----------+--------------+
              |                          |
      Vozes do Chrome              Motor local
        chrome.tts                       |
              |                Documento offscreen
              |                          |
              |                 FastAPI :8765
              |                          |
              |               Qwen3-TTS VoiceDesign
              |                          |
              |                     Áudio WAV
              |                          |
              |              Blob + elemento <audio>
              +------------+-------------+
                           |
                  Reprodução no Chrome
```

## Componentes

- `extension/popup.html`, `popup.css`, `popup.js`: mensagem digitada, preferências, lista de vozes PT-BR, descrição de voz e controles. Fechar o popup não interrompe a reprodução.
- `extension/settings.js`: valores padrão, normalização de configurações e validação do texto.
- `extension/background.js`: menu de contexto, fila de comandos, roteamento de motores, controle do Chrome TTS e estado em `storage.session`. Cada leitura tem um identificador para descartar eventos de leituras antigas.
- `extension/offscreen.js`: geração local, cancelamento de fetch, reprodução e liberação de URLs Blob. Retorna imediatamente ao comando de início e informa andamento por mensagens. Assim o popup não precisa permanecer aberto durante a geração.
- `backend/`: FastAPI e Qwen3-TTS, carregado sob demanda na primeira síntese.

A extensão requer Chrome 116+ para consultar os contextos offscreen. As razões de criação são `AUDIO_PLAYBACK` e `BLOBS`: URLs Blob são usadas na reprodução, e o contexto precisa sobreviver durante gerações sem áudio que podem durar minutos. O documento permanece disponível para novas leituras; ao parar ou concluir, libera áudio e URLs. A espera pela geração tem limite de 15 minutos. Cancelar a requisição no cliente não interrompe a inferência síncrona já iniciada no backend.

## API local

- `GET /health`: disponibilidade do servidor, sem carregar o modelo.
- `GET /v1/voices`: perfis de voz.
- `GET /v1/styles`: estilos de narração.
- `POST /v1/speech`: recebe `text`, `voice`, `style` e `instruction` opcional; retorna WAV.

A descrição personalizada substitui o timbre do perfil base, mantendo as regras de português brasileiro e o estilo de narração. O perfil base é usado quando a descrição está vazia. O modelo padrão é `Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign`; português brasileiro é orientado por instruções, sujeito à qualidade do modelo.

O motor serializa a carga e as gerações com um lock. Cada texto é dividido por frases/palavras em trechos limitados por `VOXARCANA_CHUNK_CHARS` (350 por padrão), sintetizados individualmente e unidos com pausas de 150 ms. Em GPUs com até 8 GiB, o modo automático move o decodificador de áudio para CPU/float32 e atualiza o dispositivo armazenado pelo wrapper do tokenizer. A geração de códigos permanece na GPU. `VOXARCANA_DECODER_DEVICE` permite selecionar explicitamente o dispositivo do decodificador. A seleção automática de dtype verifica suporte a bfloat16, usando float16 nas GPUs CUDA que não o oferecem. O alocador CUDA usa segmentos expansíveis por padrão, respeitando uma configuração externa já existente.

## Persistência e acesso

Configurações ficam em `chrome.storage.local`. O texto digitado e o estado ficam em `chrome.storage.session`, que sobrevive ao fechamento do popup e à suspensão do service worker, mas é limpo com o encerramento do navegador ou recarga da extensão.

Não há scripts injetados, leitura automática das páginas nem dependências JavaScript externas. O único host autorizado é `127.0.0.1:8765`. Vozes do Chrome podem ser fornecidas pelo sistema ou por outros mecanismos, inclusive remotos.

## Evolução

Clonagem com referência aprovada, identidade persistente, streaming e inicialização automática do motor via Native Messaging permanecem como etapas futuras. O uso atual do motor local exige iniciar o backend manualmente.
