# Arquitetura do VoxArcana

## Escopo do MVP

O primeiro objetivo é validar um fluxo completamente local:

```text
Texto selecionado no navegador
        |
        v
Extensão Chromium
        |
        | HTTP localhost
        v
FastAPI :8765
        |
        v
Qwen3-TTS VoiceDesign
        |
        v
WAV
        |
        v
Reprodução no navegador
```

## Componentes

### `extension/`

Extensão Manifest V3.

No MVP:

- adiciona `Narrar com VoxArcana` ao menu de contexto;
- envia o texto selecionado à API local;
- recebe WAV;
- usa um documento offscreen para reproduzir o áudio.

### `backend/`

Serviço local em Python/FastAPI.

Endpoints iniciais:

- `GET /health`
- `GET /v1/voices`
- `POST /v1/speech`

O modelo é carregado somente na primeira geração de áudio.

### Motor inicial

Modelo padrão:

`Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign`

O Qwen3-TTS suporta português e Voice Design por instrução textual. A fase seguinte deve gerar uma voz de referência aprovada e convertê-la em um perfil reutilizável via Voice Clone para manter identidade consistente.

## Próximas fases

1. Gerar candidatos para o narrador épico.
2. Escolher e congelar a voz aprovada.
3. Adicionar configuração de voz e estilo na extensão.
4. Criar perfis masculino e feminino.
5. Avaliar identificação de falas/personagens no HTML da página.
6. Adicionar cache e streaming para reduzir latência.
7. Avaliar integração como mecanismo TTS do Chromium.
