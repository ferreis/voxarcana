# VoxArcana

VoxArcana é um projeto de TTS local voltado para narração imersiva de RPG no navegador.

## Objetivo inicial

- Ler texto selecionado em páginas web.
- Usar TTS local, sem assinatura e sem API paga.
- Priorizar português brasileiro.
- Criar vozes reutilizáveis para narrador e personagens.
- Permitir estilos como fantasia épica, suspense, terror e narração neutra.
- Integrar o motor local com uma extensão Chromium.

## Arquitetura prevista

```text
Navegador / Extensão
        |
        v
VoxArcana Local API
        |
        v
Motor TTS
        |
        +-- Qwen3-TTS
        +-- outros motores no futuro
```

## Primeira fase

1. Subir uma API local.
2. Integrar Qwen3-TTS.
3. Gerar e testar vozes em PT-BR.
4. Criar um perfil de narrador de fantasia épica.
5. Conectar a extensão ao serviço local.
6. Adicionar personagens e múltiplas vozes depois que o fluxo básico estiver estável.

## Estado

Projeto em fase inicial.
