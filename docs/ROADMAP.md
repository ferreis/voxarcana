# Roadmap

## Fase 1 — MVP local

- [x] Criar estrutura do repositório.
- [x] Criar API local.
- [x] Criar integração inicial com Qwen3-TTS VoiceDesign.
- [x] Criar extensão Chromium para texto selecionado.
- [x] Executar o projeto em uma máquina real.
- [ ] Validar CUDA/VRAM ou definir fallback.
- [x] Gerar primeira amostra de narrador em português.
- [x] Reforçar português brasileiro no perfil de voz.
- [x] Separar voz de estilo de narração.
- [x] Criar 10 estilos iniciais.

## Estilos iniciais

- [x] Fantasia Épica
- [x] Terror
- [x] Ação
- [x] Suspense
- [x] Mistério
- [x] Calmo
- [x] Detetive Noir
- [x] Contador de Histórias
- [x] Documentário
- [x] Neutro

## Fase 2 — Voz persistente

- [ ] Gerar múltiplos candidatos do Narrador BR.
- [ ] Selecionar a voz final.
- [ ] Salvar áudio de referência e transcrição.
- [ ] Migrar geração principal para Qwen3-TTS Base + Voice Clone.
- [ ] Cachear o voice clone prompt.

## Fase 3 — Extensão

- [x] Criar janela com caixa de texto e configurações.
- [x] Selecionar vozes PT-BR do Chrome ou perfil local.
- [x] Selecionar estilo e descrição de voz personalizada.
- [ ] Configurar atalho de teclado.
- [x] Adicionar parar/pausar/continuar.
- [x] Exibir erros de conexão com a API local.
- [x] Salvar preferências e rascunho durante a sessão.
- [x] Manter reprodução com o popup fechado.

## Fase 4 — RPG

- [x] Perfil base de narrador.
- [ ] Perfil masculino.
- [ ] Perfil feminino.
- [ ] Cadastro de vozes por personagem.
- [ ] Investigar identificação automática de diálogo.
- [ ] Investigar leitura de metadados/HTML do site para identificar personagem.
