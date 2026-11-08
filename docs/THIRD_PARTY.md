# Modelos e gravações de referência

## Chatterbox PT-BR

- Autoria: Resemble AI.
- Checkpoint: https://huggingface.co/ResembleAI/Chatterbox-Multilingual-pt-br
- Licença declarada pelo autor: MIT.
- Revisão do checkpoint: `b3952f18bc2eaa72b9bd7c17d2c4653bcad4770d`.
- Código de inferência: https://huggingface.co/spaces/ResembleAI/Chatterbox-Multilingual-TTS-pt-br
- Revisão do carregador: `9e515821e826e207cd617a0fdd0223899ed108ea`.
- Encoder compartilhado: `ResembleAI/chatterbox`, revisão `5bb1f6ee58e50c3b8d408bc82a6d3740c2db6e18`, arquivo `ve.pt`.
- Código/licença de origem: https://github.com/resemble-ai/chatterbox/blob/master/LICENSE

Os arquivos de inferência são baixados sem alterações para `backend/models/chatterbox-br-source`; o adaptador local importa esse pacote com um nome isolado. A execução usa a classe do demo para carregar pesos locais e evita a busca automática por pesos de outra versão. O código e os pesos não são redistribuídos no Git deste projeto.

A referência feminina é o áudio `pt_br_f2.wav` selecionado pelo próprio demo oficial, disponibilizado em https://storage.googleapis.com/chatterbox-demo-samples/mtl-v3-single-language-prompts/pt-br/pt_br_f2.wav . A licença MIT do modelo não deve ser interpretada como uma autorização independente para qualquer uso de identidade vocal; para uma identidade própria, forneça uma gravação autorizada.

## TTS-Portuguese Corpus

- Autores do corpus: Edresson Casanova e colaboradores; referência completa no repositório/artigo do corpus.
- Fonte: https://github.com/Edresson/TTS-Portuguese-Corpus
- Demonstração com gravações originais: https://edresson.github.io/TTS-Portuguese-Corpus/
- Licença do corpus: Creative Commons Attribution 4.0 International (CC BY 4.0).
- Texto da licença: https://creativecommons.org/licenses/by/4.0/
- Publicação: https://arxiv.org/abs/2005.05144
- Revisão dos arquivos de áudio: `6492e5a6b2d55db4060c7c36beb232e90c6d712b` (`gh-pages`).

A referência masculina `narrador-br.wav` é uma adaptação dos arquivos de fala **original** `audio/Esperado/1.wav`, `2.wav` e `3.wav`. O script junta essas três gravações, acrescenta pausas de 150 ms e salva em WAV PCM16. Não usa as amostras sintetizadas dos experimentos. A descrição da voz na interface atribui o corpus e a licença; esta nota identifica as mudanças realizadas. Não há afiliação, aprovação ou promessa de endosso pelos autores.

## Dependências

As bibliotecas de frontend e Python mantêm suas próprias licenças. `frontend/package-lock.json` fixa a resolução do frontend; `backend/requirements-br.txt` lista as dependências do carregador brasileiro. As gravações enviadas pelo usuário permanecem locais e não entram no repositório.
