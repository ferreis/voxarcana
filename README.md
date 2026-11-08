# VoxArcana Studio

Estúdio local de narração para RPG, aberto em uma aba do navegador. Cole a cena, escolha uma voz brasileira, gere o áudio e ouça ou baixe o WAV, sem créditos nem assinatura.

## Abrir o estúdio

Com o servidor iniciado, abra **http://127.0.0.1:8765**. A extensão não é necessária para usar o estúdio.

Para preparar uma instalação nova, na raiz do projeto:

```bash
bash scripts/setup-br.sh
bash scripts/start-studio.sh
```

O setup instala o ambiente isolado `backend/.venv-br`, baixa o modelo e as referências e compila a interface. Requer Python 3.10+, Node compatível com o Vite instalado e espaço para os pesos/dependências (reserve cerca de 12 GB). O modelo pode usar a GPU NVIDIA ou CPU; na CPU, a geração é mais lenta. A distribuição PyTorch usada pelo script é CUDA 12.4, com suporte à RTX 2060 testada neste projeto.

O comando de início mantém o servidor no terminal. Para encerrar, use `Ctrl+C`. Ele aceita conexões apenas deste computador, em `127.0.0.1`.

## Vozes brasileiras

O motor do estúdio é o **[Chatterbox Multilingual PT-BR](https://huggingface.co/ResembleAI/Chatterbox-Multilingual-pt-br)**, um ajuste dedicado a português brasileiro. O idioma é fixado em `pt` conforme o carregador oficial desse checkpoint; isso não seleciona o modelo de Portugal. O antigo Qwen VoiceDesign era multilíngue e dependia de instruções para tentar manter o sotaque brasileiro.

Há duas referências iniciais:

- **Narrador brasileiro:** gravações reais masculinas do [TTS-Portuguese Corpus](https://github.com/Edresson/TTS-Portuguese-Corpus), sob CC BY 4.0. É uma referência de voz, não uma promessa de interpretação profissional de audiobook.
- **Brasileira · demonstração:** gravação feminina usada na demonstração oficial do modelo PT-BR.

Você pode ouvir a gravação original na seção da voz antes de gerar. Para buscar outro timbre, clique em **Adicionar minha voz** e envie uma gravação brasileira de 3 a 30 segundos, em WAV ou FLAC, com até 10 MB. Prefira fala limpa, sem música, ruído ou outras pessoas. Use uma gravação sua ou autorizada. O servidor valida o áudio, salva uma versão mono e permite selecionar essa referência nas próximas sessões.

O timbre vem da referência de áudio. O Chatterbox não usa a descrição textual de voz do Qwen. A seleção de interpretação ajusta a expressividade; não controla emoções com a mesma precisão de uma direção humana. O modelo específico e uma boa referência brasileira melhoram a escolha de sotaque, mas a naturalidade e a pronúncia devem ser conferidas por escuta. Não se promete qualidade equivalente ao ElevenLabs.

O projeto Chatterbox foi arquivado pelo fornecedor em agosto de 2026; o código e os pesos continuam disponíveis sob MIT. Este projeto fixa as revisões do carregador e do checkpoint em `scripts/download-br.py`, usando os arquivos do demo PT-BR para manter a compatibilidade com seu decodificador V3. Detalhes e atribuições: [docs/THIRD_PARTY.md](docs/THIRD_PARTY.md).

## Usar durante a sessão

1. Cole ou escreva até 10.000 caracteres e dê um título à cena.
2. Escolha a referência de voz e a interpretação.
3. Clique em **Gerar narração** e acompanhe os trechos concluídos.
4. Quando estiver pronta, use o player para ouvir, pausar, mudar a velocidade ou baixar o WAV.

A geração roda no servidor e continua se a página for recarregada. A aba salva o identificador para recuperar o trabalho ao reabrir o mesmo endereço. **Cancelar** interrompe a geração ao terminar o trecho em processamento; não remove a voz ou o rascunho.

O processamento é sequencial para evitar gerações simultâneas na GPU. O estúdio aceita até três trabalhos ativos/na fila e divide textos em trechos de até 280 caracteres para limitar o consumo de memória. Pode haver variações de entonação entre trechos.

## Dados locais

- Texto, título, seleção de voz e identificador do último trabalho: `localStorage` do navegador, neste endereço. Se o armazenamento estiver indisponível, a página continua funcionando sem salvar o rascunho.
- Gravações adicionadas: `backend/voices/references/`, ignoradas pelo Git.
- Pesos, carregador e referências iniciais: `backend/models/`, ignorados pelo Git.
- Narrações prontas: memória do servidor, com retenção limitada; reiniciar o servidor remove os trabalhos/áudios. Baixe o WAV para guardar uma narração.

O áudio é gerado localmente. Depois da instalação, o motor não precisa enviar o texto para um serviço pago. O modelo aplica sua marca d'água de procedência. A primeira geração carrega os pesos e pode levar mais tempo.

## Desenvolvimento do frontend

A interface usa Vue 3, TypeScript, Vite e Tailwind CSS 4. A produção é servida pelo próprio FastAPI, sem precisar de outro servidor para a interface.

```bash
npm --prefix frontend ci
npm --prefix frontend run dev
# ou compilar a versão servida em :8765
npm --prefix frontend run build
```

O Vite encaminha `/v1` e `/health` para o backend local. A aplicação é uma única tela; não usa Router nem uma store global sem necessidade. Os serviços HTTP ficam em `frontend/src/services/`, a orquestração em `composables/` e os controles de áudio/referência em `components/`.

Verificações:

```bash
npm --prefix frontend run build
node --test tests/extension.test.cjs
# Para os testes de API, instale httpx no ambiente que os executará:
backend/.venv-br/bin/python -m pip install httpx
backend/.venv-br/bin/python -m unittest discover -s tests -p 'test_*.py'
```

## Extensão e Qwen anteriores

O diretório `extension/` continua disponível como opção de leitura de texto selecionado ou digitado no popup. Carregue essa pasta em `chrome://extensions`, no modo do desenvolvedor. A extensão usa o mesmo backend em `127.0.0.1:8765` quando você escolhe o motor local. Para usar Chatterbox, deixe sua antiga descrição textual de voz em branco; a identidade agora vem da referência cadastrada no estúdio. Os perfis cadastrados podem ser atualizados no popup pelo botão de verificar o motor local.

Para usar o Qwen anterior, prepare `bash scripts/setup-dev.sh` e inicie explicitamente:

```bash
cd backend
source .venv/bin/activate
VOXARCANA_ENGINE=qwen python -m uvicorn app.main:app --host 127.0.0.1 --port 8765
```

Os ambientes são separados porque as versões de Transformers exigidas pelos dois carregadores são diferentes. Não instale as dependências do Chatterbox dentro de `.venv`. O script `scripts/download-model.sh` continua sendo o download do Qwen, não do modelo brasileiro.

Ajustes do Qwen para GPUs pequenas: `VOXARCANA_DECODER_DEVICE=auto` move a conversão para áudio à CPU em GPUs de até 8 GiB; `VOXARCANA_CHUNK_CHARS=350` limita trechos; `VOXARCANA_DTYPE=auto` seleciona float16 em GPUs sem bfloat16 nativo. Esses ajustes não resolvem, por si só, o sotaque.
