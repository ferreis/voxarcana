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
VoxArcana Local API
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

## MVP atual

O repositório já contém:

- API local com FastAPI;
- integração inicial com Qwen3-TTS VoiceDesign;
- perfil de Narrador de Fantasia Épica;
- perfil de Narrador de Mistério;
- extensão Chromium Manifest V3;
- menu de contexto `Narrar com VoxArcana`;
- reprodução do áudio em documento offscreen.

## Executar o backend

Requer Python 3.12.

```bash
git clone https://github.com/ferreis/voxarcana.git
cd voxarcana/backend

python3.12 -m venv .venv
source .venv/bin/activate

pip install -U pip
pip install -e .

cp .env.example .env

uvicorn app.main:app --host 127.0.0.1 --port 8765
```

Teste:

```bash
curl http://127.0.0.1:8765/health
```

Resposta esperada:

```json
{"status":"ok"}
```

O modelo do Qwen é carregado apenas na primeira geração. Na primeira execução, os pesos também podem precisar ser baixados.

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

A API precisa estar rodando em `127.0.0.1:8765`.

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

Depois disso entram os perfis masculino, feminino e vozes específicas por personagem.

Consulte [docs/ROADMAP.md](docs/ROADMAP.md) e [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
