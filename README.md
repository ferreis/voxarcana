# VoxArcana

VoxArcana é um projeto de TTS local voltado para narração imersiva de RPG no navegador.

## Objetivo

- Ler texto selecionado em páginas web.
- Usar TTS local, sem assinatura e sem API paga.
- Priorizar português brasileiro.
- Criar vozes reutilizáveis para narrador e personagens.
- Permitir estilos como fantasia épica, suspense, terror e narração neutra.
- Integrar o motor local com uma extensão Chromium.

## Arquitetura

```text
Texto selecionado
      |
      v
Extensão Chromium
      |
      v
VoxArcana Local API (protótipo)
      |
      v
Qwen3-TTS
      |
      v
Áudio WAV
      |
      v
Navegador
```

> A API HTTP é apenas a arquitetura de desenvolvimento inicial. A versão final deve iniciar o engine local automaticamente via Native Messaging, sem exigir que o usuário abra um backend manualmente.

## MVP atual

O repositório já contém:

- API local com FastAPI;
- integração inicial com Qwen3-TTS VoiceDesign;
- perfil de Narrador de Fantasia Épica;
- perfil de Narrador de Mistério;
- extensão Chromium Manifest V3;
- menu de contexto `Narrar com VoxArcana`;
- reprodução do áudio em documento offscreen.

## Executar o backend de desenvolvimento

Requer Python 3.10 ou superior.

```bash
git clone git@github.com:ferreis/voxarcana.git
cd voxarcana

./scripts/setup-dev.sh
```

Depois:

```bash
cd backend
source .venv/bin/activate
python -m uvicorn app.main:app --host 127.0.0.1 --port 8765
```

Teste em outro terminal:

```bash
curl http://127.0.0.1:8765/health
```

Resposta esperada:

```json
{"status":"ok"}
```

## Baixar o modelo localmente

O Transformers usado pelo projeto exige `huggingface-hub >=0.34,<1.0`.

Use o script do projeto:

```bash
cd ~/Documentos/Projetos/voxarcana
git pull
./scripts/download-model.sh
```

O script baixa o modelo público sem enviar tokens Hugging Face salvos no computador. Isso evita erros `401` causados por tokens antigos, inválidos ou expirados.

Depois configure `backend/.env`:

```env
VOXARCANA_MODEL=./models/Qwen3-TTS-12Hz-1.7B-VoiceDesign
```

O modelo ocupa aproximadamente 4,5 GB.

## Instalar a extensão

No Chrome/Chromium:

1. Abra `chrome://extensions`.
2. Ative **Modo do desenvolvedor**.
3. Clique em **Carregar sem compactação**.
4. Selecione a pasta `extension/`.
5. Abra qualquer página.
6. Selecione um texto.
7. Clique com o botão direito.
8. Escolha **Narrar com VoxArcana**.

Durante o MVP, a API de desenvolvimento precisa estar rodando em `127.0.0.1:8765`.

## Configuração de hardware

O padrão usa detecção automática:

```env
VOXARCANA_DEVICE=auto
VOXARCANA_DTYPE=auto
VOXARCANA_ATTN=sdpa
```

Se houver GPU NVIDIA compatível:

```env
VOXARCANA_DEVICE=cuda:0
VOXARCANA_DTYPE=bfloat16
VOXARCANA_ATTN=flash_attention_2
```

O FlashAttention é opcional e exige instalação separada.

## Próximo objetivo

Gerar várias amostras de **Narrador de Fantasia Épica em PT-BR**, escolher uma voz e transformá-la em uma identidade persistente usando o fluxo:

```text
Voice Design
    |
    v
voz aprovada.wav
    |
    v
Voice Clone
    |
    v
Narrador VoxArcana
```

Depois disso, substituir a API HTTP por um engine local iniciado automaticamente pela extensão e adicionar os perfis masculino, feminino e vozes específicas por personagem.

Consulte [docs/ROADMAP.md](docs/ROADMAP.md) e [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
