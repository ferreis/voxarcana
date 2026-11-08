# VoxArcana

Extensão do Google Chrome/Chromium para ler mensagens digitadas ou textos selecionados em português brasileiro.

- **Vozes do Chrome:** lê sem iniciar o backend, usando as vozes PT-BR disponíveis no navegador/sistema. Algumas vozes precisam de internet; a disponibilidade varia, especialmente no Linux.
- **Voz personalizada local:** usa Qwen3-TTS para gerar narração com descrição de timbre, sotaque e emoção, além de dez estilos de leitura. Requer o backend Python e o modelo no computador, sem API paga.
- Caixa de texto com até 10.000 caracteres, seleção de voz, velocidade, pausar, continuar e parar.
- Configurações salvas no computador. O rascunho permanece durante a sessão do navegador e é removido ao encerrar o Chrome ou recarregar/desativar a extensão.
- A reprodução continua quando você fecha a janela da extensão.

## Instalar e usar no Chrome

Requer Chrome/Chromium 116 ou superior.

1. Abra `chrome://extensions`.
2. Ative **Modo do desenvolvedor**.
3. Clique em **Carregar sem compactação** e selecione a pasta `extension/` deste projeto.
4. Fixe o VoxArcana pelo menu de extensões do Chrome e clique no ícone.
5. Escreva ou cole a mensagem na caixa de texto.
6. Selecione **Vozes do Chrome** e uma voz brasileira. Clique em **Ler mensagem**.

Se já instalou uma versão anterior, clique em **Recarregar** no cartão da extensão em `chrome://extensions`.

Se não aparecer nenhuma voz brasileira, clique em **Atualizar vozes** após instalar/habilitar uma voz PT-BR no sistema ou um mecanismo TTS para Chrome. Você também pode usar o motor local abaixo. A extensão não substitui português brasileiro por uma voz de outro idioma silenciosamente.

Para ler em uma página, selecione um trecho, clique com o botão direito e escolha **Narrar com VoxArcana**. Esse menu usa o motor, a voz e o estilo salvos na janela da extensão. Em caso de falha, um `!` aparece no ícone; abra a extensão para ver a mensagem.

## Usar uma voz personalizada em PT-BR

1. Inicie o backend conforme as instruções abaixo.
2. Na extensão, selecione **Voz personalizada · motor local**.
3. Clique em **Verificar motor local** para conferir a conexão e atualizar os perfis/estilos disponíveis.
4. Escolha um estilo, como **Neutro**, **Fantasia Épica**, **Calmo** ou **Mistério**.
5. Em **Como a voz deve soar?**, descreva a voz. Exemplo:

   > Voz feminina adulta, brasileira, suave e acolhedora, com sotaque brasileiro neutro e dicção clara.

6. Clique em **Ler mensagem**.

A descrição substitui o timbre do perfil base, preservando as instruções de português brasileiro e o estilo escolhido. Deixe em branco para usar o Narrador BR padrão. A tonalidade é ajustável nas vozes do Chrome; a velocidade está disponível nos dois motores e, no motor local, é aplicada à reprodução do áudio.

**Limite atual:** Voice Design gera voz por descrição; a identidade pode variar entre leituras e o sotaque precisa ser conferido na prática. Clonagem por gravação e identidade persistente ainda não foram implementadas. A primeira geração carrega o modelo e pode levar minutos, sobretudo em CPU. Parar cancela a espera/reprodução na extensão; uma geração já iniciada pode continuar consumindo recursos no servidor até terminar.

## Executar o backend local (opcional)

Requer Python 3.10 ou superior. Na raiz do projeto:

```bash
./scripts/setup-dev.sh
cd backend
source .venv/bin/activate
python -m uvicorn app.main:app --host 127.0.0.1 --port 8765
```

Confira em outro terminal:

```bash
curl http://127.0.0.1:8765/health
```

Resposta esperada: `{"status":"ok"}`. Isso confirma que a API está disponível; o modelo só é carregado na primeira geração.

### Baixar o modelo antes da primeira leitura

O modelo padrão é `Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign`, com aproximadamente 4,5 GB. Na raiz do projeto:

```bash
./scripts/download-model.sh
```

O script baixa o modelo público sem enviar tokens Hugging Face salvos no computador, evitando erros de tokens antigos. Configure `backend/.env`:

```env
VOXARCANA_MODEL=./models/Qwen3-TTS-12Hz-1.7B-VoiceDesign
VOXARCANA_DEVICE=auto
VOXARCANA_DTYPE=auto
VOXARCANA_ATTN=sdpa
VOXARCANA_DECODER_DEVICE=auto
VOXARCANA_CHUNK_CHARS=350
```

O Transformers usado pelo projeto exige `huggingface-hub >=0.34,<1.0`. O padrão detecta GPU NVIDIA ou usa CPU. Para uma GPU compatível, é possível configurar `VOXARCANA_DEVICE=cuda:0` e `VOXARCANA_DTYPE=bfloat16`. FlashAttention é opcional e exige instalação separada.

### Placas com pouca VRAM

Em GPUs com até 8 GiB, `VOXARCANA_DECODER_DEVICE=auto` mantém o modelo de voz na GPU e converte seus códigos em áudio na CPU, reduzindo os picos de VRAM. `VOXARCANA_DECODER_DEVICE=cpu` força essa configuração em qualquer placa. A seleção automática de precisão usa `float16` em GPUs sem suporte a `bfloat16`, como a RTX 2060.

Os textos são processados sequencialmente em trechos de até 350 caracteres e unidos em um WAV. O limite pode ser ajustado com `VOXARCANA_CHUNK_CHARS` (100 a 2.000). Isso limita o consumo de memória por trecho; a voz por descrição ainda pode variar entre eles. Requisições simultâneas aguardam sua vez, sem executar duas gerações na mesma GPU. Se outras aplicações ocuparem a VRAM necessária, use `VOXARCANA_DEVICE=cpu` e `VOXARCANA_DTYPE=float32` e reinicie o backend; a leitura será mais lenta.

## Dados e permissões

A extensão usa `tts`, `storage`, `contextMenus` e `offscreen`. Só solicita acesso HTTP a `http://127.0.0.1:8765/*`; não injeta scripts nem lê automaticamente o conteúdo das páginas. O menu de contexto recebe apenas o texto selecionado que você pediu para narrar.

No modo local, texto e descrição são enviados ao backend em loopback. No modo Chrome, o tratamento do texto depende da voz escolhida, que pode usar um serviço online. O modelo pode precisar de internet para o primeiro download. Preferências e descrição da voz ficam em `storage.local`; o rascunho e o estado de reprodução ficam em `storage.session`.

## Verificações de desenvolvimento

Os testes de controle da extensão usam simulações das APIs do Chrome e não exigem instalar o modelo:

```bash
node --test tests/extension.test.cjs
backend/.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
```

Para conferir a reprodução real, carregue a extensão no Chrome e teste uma frase curta nos dois modos. A qualidade da voz personalizada depende do modelo e do hardware.

Consulte [docs/ROADMAP.md](docs/ROADMAP.md) e [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
