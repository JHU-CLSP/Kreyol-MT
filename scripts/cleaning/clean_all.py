import glob
import os
import sys
import click
import pathlib
from tqdm import tqdm
import copy
import pdb

# This is to utilize some pre-built config files that our from previous projects.
LANG_CODE_MAP = {
    'eng': 'en-US',
    'spa': 'es-ES',
    'fra': 'fr-FR',
    'por': 'pt-BR',
    'ara': 'ar-EG',
    'zho': 'zh-CN',
    'ceb': 'ceb-PH',
    'deu': 'de-DE',
    'nep': 'ne-NP',
    'tpi': 'tpi-PG',
    'hat': 'hat-HT',
    'pap': 'pap-AN',
}

@click.command(
    help="Clean the generated per-lang train datasets in a directory with subdirectories titled [src]--[tgt]"
)
@click.argument(
    "data_dir",
    type=click.Path(exists=True, file_okay=False, path_type=pathlib.Path),
)
@click.argument(
    "output_dir",
    type=click.Path(writable=True, file_okay=False, path_type=pathlib.Path),
)
@click.option(
    "--clean_train",
    default=True,
    help="Clean the train data",
    type=bool,
)
def main(
    data_dir: pathlib.Path,
    output_dir: pathlib.Path,
    clean_train: bool,
):
    # Get list of train.[src] and train.[tgt] files
    lang_pair_dirs = list(data_dir.glob("**/*--*"))

    os.chdir('data-cleaning-pipeline')

    total_lang_pairs = len(lang_pair_dirs)

    for lang_pair_dir in tqdm(lang_pair_dirs, desc="Cleaning", total=total_lang_pairs, file=sys.stdout):
        test_output_dir = os.path.join(output_dir, 'test')
        dev_output_dir = os.path.join(output_dir, 'dev')
        clean_pair(lang_pair_dir, test_output_dir, 'test')
        clean_pair(lang_pair_dir, dev_output_dir, 'dev')
    
        if clean_train:
            train_output_dir = os.path.join(output_dir, 'train')
            clean_pair(lang_pair_dir, train_output_dir, 'train')

        try:
            # Remove duplicates
            train_fns = glob.glob(os.path.join(lang_pair_dir, 'train*'))
            if not train_fns:
                continue
            langs = list(set([fn.split('.')[-1] for fn in train_fns]))
            lang1, lang2 = tuple(langs)
            lang2splits = {lang1: {}, lang2: {}}
            for lang in [lang1, lang2]:
                for split in ['train', 'dev']:
                    split_path = os.path.join(lang_pair_dir, f'{split}.cleaned.{lang}')
                    lang2splits[lang][split] = []
                    if os.path.exists(split_path):
                        with open(split_path, 'r') as f:
                            lang2splits[lang][split] = f.readlines()
                test_paths = glob.glob(os.path.join(lang_pair_dir, f'*test*.{lang}'))
                test_segs = []
                for test_path in test_paths:
                    with open(test_path, 'r') as f:
                        test_segs += f.readlines()
                lang2splits[lang]['test'] = test_segs
            for lang in [lang1, lang2]:
                for split in ['train', 'dev']:
                    original_len = len(lang2splits[lang][split])
                    lines = [lang2splits[lang][split][i] for i in range(original_len) if \
                            lang2splits[lang1][split][i] not in lang2splits[lang1]['test'] and \
                            lang2splits[lang2][split][i] not in lang2splits[lang2]['test']
                            ]
                    final_len = len(lines)
                    with open(os.path.join(output_dir, f'{split}.cleaned.{lang}'), 'w') as f:
                        f.writelines(lines)
                    if original_len:
                        percent = round(100 * (original_len - final_len) / original_len, 1)
                    else:
                        percent = 0
                    print(f'Removed {original_len - final_len} lines in deduplication'\
                          f' ({percent}%) for {lang1}--{lang2}')
        except:
            print("ERROR found with", lang_pair_dir)

    os.chdir('..')

def clean_pair(lang_pair_dir: pathlib.Path, output_dir: pathlib.Path, data_type: str):
    if data_type == 'train':
        src_path = os.path.join(lang_pair_dir, 'train.' + lang_pair_dir.name.split('--')[0])
        tgt_path = os.path.join(lang_pair_dir, 'train.' + lang_pair_dir.name.split('--')[1])
    elif data_type == 'dev':
        src_path = os.path.join(lang_pair_dir, 'dev.' + lang_pair_dir.name.split('--')[0])
        tgt_path = os.path.join(lang_pair_dir, 'dev.' + lang_pair_dir.name.split('--')[1])
    elif data_type == 'test':
        src_path = os.path.join(lang_pair_dir, 'test.' + lang_pair_dir.name.split('--')[0])
        tgt_path = os.path.join(lang_pair_dir, 'test.' + lang_pair_dir.name.split('--')[1])

    # Check if the files exist
    if not os.path.exists(src_path):
        print(f"Could not find {src_path}", file=sys.stderr)
        return
    if not os.path.exists(tgt_path):
        print(f"Could not find {tgt_path}", file=sys.stderr)
        return

    # Check if the files are empty
    if os.stat(src_path).st_size == 0:
        print(f"Empty file {src_path}", file=sys.stderr)
        return
    if os.stat(tgt_path).st_size == 0:
        print(f"Empty file {tgt_path}", file=sys.stderr)
        return

    # Extract the language codes for the cleaning pipeline
    src_lang = lang_pair_dir.name.split('--')[0]
    tgt_lang = lang_pair_dir.name.split('--')[1]

    print(f"Cleaning {src_lang}--{tgt_lang}", file=sys.stdout)

    if src_lang in LANG_CODE_MAP: src_lang = LANG_CODE_MAP[src_lang]
    if tgt_lang in LANG_CODE_MAP: tgt_lang = LANG_CODE_MAP[tgt_lang]

    # Create the output directory
    output_path = os.path.join(output_dir, lang_pair_dir.name)

    if not os.path.exists(output_path):
        os.makedirs(output_path)
    
    os.system(f'python3 pipeline.py -t {output_path} -srclang {src_lang} -tgtlang {tgt_lang} -srcpath {src_path} -tgtpath {tgt_path} -d')

    

if __name__ == '__main__':
    main()
