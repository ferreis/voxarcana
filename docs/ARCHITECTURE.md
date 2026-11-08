# Arquitetura do VoxArcana

## Estúdio local

```text
Aba do navegador (Vue 3 + TypeScript)
           |
           | POST /v1/jobs + consulta de andamento
           v
FastAPI 127.0.0.1:8765 ── serve frontend/dist em /
           |
           v
Fila limitada, uma geração por vez
           |
           v
Chatterbox PT-BR + referência brasileira
           |
           | trechos <=280 caracteres, idioma pt do checkpoint PT-BR
           v
WAV em memória ── /v1/jobs/{id}/audio ── player / download
```

`frontend/src/services/studio.ts` concentra HTTP. `composables/useStudio.ts` coordena configuração, rascunho local, envio, polling, reconexão, cancelamento e limpeza. Os componentes de áudio e de cadastro de referência cuidam da apresentação e de suas interações.

`backend/app/brazilian.py` carrega o checkpoint específico de PT-BR com o código do demo oficial fixado por revisão, baixado por `scripts/download-br.py`. As importações ficam em um namespace isolado para evitar conflito com outros pacotes `chatterbox`. A carga ocorre em CPU antes da movimentação dos pesos para GPU. O arquivo `narrador-br.wav` oferece uma referência masculina brasileira de corpus aberto; outra referência é a gravação feminina do demo PT-BR. Uma descrição em linguagem natural não substitui a referência neste motor.

`backend/app/jobs.py` mantém até três trabalhos ativos e uma fila de execução única. Atualizações são protegidas por lock. O cancelamento é cooperativo, verificado antes e depois de cada trecho; uma geração do modelo já em curso termina antes de ser descartada. Áudios concluídos têm retenção limitada em memória, expiram ao reiniciar o servidor e podem ser removidos ao enviar novos trabalhos após uma hora ou quando o limite de retenção é atingido.

As referências do usuário são validadas por tamanho e duração, decodificadas, convertidas em mono e armazenadas sob identificadores UUID em `backend/voices/references`. O nome original do arquivo nunca vira caminho de leitura. O servidor escuta em loopback. Escritas HTTP com Origin são limitadas às origens locais conhecidas e a extensões Chrome; CORS não é uma autenticação e este servidor não foi feito para exposição pública.

## API

- `GET /health`: disponibilidade e motor selecionado.
- `GET /v1/engine`: capacidades e instalação do motor.
- `GET /v1/voices`, `GET /v1/styles`: catálogo.
- `POST /v1/voices/reference`: cadastro de referência WAV/FLAC.
- `GET /v1/voices/{id}/reference`: ouvir a gravação original.
- `POST /v1/jobs`: enfileira narração brasileira.
- `GET /v1/jobs/{id}`: andamento e erro.
- `DELETE /v1/jobs/{id}`: pede cancelamento.
- `GET /v1/jobs/{id}/audio`: WAV concluído.
- `POST /v1/speech`: síntese síncrona preservada para a extensão.

## Qwen e extensão anteriores

O ambiente `.venv` e a seleção `VOXARCANA_ENGINE=qwen` preservam o Qwen3-TTS VoiceDesign. `.venv-br` usa as dependências incompatíveis do carregador brasileiro. `start-studio.sh` seleciona explicitamente `chatterbox-br` e serve interface + API em um único endereço.

A extensão Manifest V3 continua com `chrome.tts` ou requisição síncrona ao backend local. Seu documento offscreen reproduz WAV/Blob sem manter o popup aberto. O menu de seleção usa as configurações salvas. A extensão não precisa ser instalada para usar o estúdio em uma aba.

Clonagem por referência é oferecida pelo motor brasileiro. A naturalidade, semelhança com o falante e consistência entre trechos precisam de validação por escuta; não são garantidas pelo locale ou por uma resposta HTTP bem-sucedida.
