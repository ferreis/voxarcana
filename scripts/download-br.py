"""Download the official PT-BR checkpoint and pinned demo loader."""
from pathlib import Path
import os

os.environ.setdefault('HF_HUB_DISABLE_IMPLICIT_TOKEN', '1')
from huggingface_hub import hf_hub_download, snapshot_download

ROOT = Path(__file__).resolve().parents[1] / 'backend'
MODEL_REPO = 'ResembleAI/Chatterbox-Multilingual-pt-br'
MODEL_REVISION = 'b3952f18bc2eaa72b9bd7c17d2c4653bcad4770d'
SOURCE_REPO = 'ResembleAI/Chatterbox-Multilingual-TTS-pt-br'
SOURCE_REVISION = '9e515821e826e207cd617a0fdd0223899ed108ea'


def main():
    source = ROOT / 'models/chatterbox-br-source'
    model = ROOT / 'models/chatterbox-ptbr'
    snapshot_download(repo_id=SOURCE_REPO, repo_type='space', revision=SOURCE_REVISION,
                      allow_patterns=['chatterbox/**'], local_dir=source, token=False)
    snapshot_download(repo_id=MODEL_REPO, revision=MODEL_REVISION,
                      allow_patterns=['t3_pt_br.safetensors', 's3gen_v3.pt',
                                      'grapheme_mtl_merged_expanded_v1.json', 'README.md'],
                      local_dir=model, token=False)
    # The voice encoder is shared with the upstream model. Pin its snapshot too.
    hf_hub_download('ResembleAI/chatterbox', 've.pt',
                    revision='5bb1f6ee58e50c3b8d408bc82a6d3740c2db6e18', local_dir=model, token=False)
    print('Modelo PT-BR:', model)
    print('Carregador oficial:', SOURCE_REVISION)


if __name__ == '__main__':
    main()
