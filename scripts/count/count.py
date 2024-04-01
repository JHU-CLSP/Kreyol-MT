import os
import glob

import pandas as pd
from pathlib import Path
import pypandoc
import json
import pdb

def count_datasets(works=None):
    langs = set(next(os.walk('.'))[1]) - set(['.git', 'scripts', 'local'])
    data = []
    for lang in langs:
        pub_sents = set()
        all_sents = set()
        if works is not None:
            work_sents = {work: set() for work in works+["Ours"]}
        pairs = next(os.walk(f'./{lang}/bitexts'))[1]
        # Add bitext datasets
        datasets = [(f, "Bitext") for pair in pairs for f in Path(f'./{lang}/bitexts/{pair}/raw').iterdir()]
        # Add mono datasets
        # NOTE: Monolingual sentence will be ignored if it already exists in a bitext dataset.
        if Path(f'./{lang}/mono/raw').exists():
            datasets = datasets + [(f, "Mono") for f in Path(f'./{lang}/mono/raw').iterdir()]
        for dataset, format in datasets:
            pub_tare = len(pub_sents)
            all_tare = len(all_sents)
            dataset_work = "Ours"
            # Identify a work
            for work in works:
                if dataset.stem.find(work) > -1:
                    dataset_work = work
                    break
            work_tare = len(work_sents[dataset_work])
            try:
                readme = pypandoc.convert_file( dataset / 'README.md', 'json')
                readme = json.loads(readme)
                public_release = readme['meta']['release']['c'][0]['c'] == 'public'
                genre = readme['meta']['genre']['c'][0]['c']
                datatype = f'{format}_{" ".join([f["c"] for f in readme["meta"]["datatype"]["c"] if "c" in f])}'
            except:
                print(f"WARNING -- Unproper 'README.md' file for {dataset}", flush=True)
                continue
            for split in dataset.glob(f'*.{lang}'):
                with open(split, 'r', encoding="utf-8") as f:
                    lines = f.readlines()
                    for line in lines:
                        work_sents[dataset_work].add(line)
                        all_sents.add(line) #lines include trailing \n, fine for counting purposes
                        if public_release:
                            pub_sents.add(line)
            data.append(
                [lang, dataset.stem, genre, datatype, public_release, 
                    len(all_sents) - all_tare, len(pub_sents) - pub_tare, 
                    dataset_work, len(work_sents[dataset_work]) - work_tare]
            )
    return pd.DataFrame(data, columns=["lang", "name", "genre", "datatype", 
                    "public", "num_lines_all", "num_lines_pub", "work", "num_lines_work"])

def classify(df, other_works):
    for work in other_works:
        df.loc[df.name.str.contains(work), "work"] = "Other"
    return df

def save_tables(df, output_folder):
    df["bitext"] = df.datatype.str.contains("Bitext")
    ## PRIOR WORK TABLE. Bitexts. Per language, release status, previous works 
    bitexts = df.loc[df["bitext"], ["lang", "work", "num_lines_work", "num_lines_pub", "num_lines_all"]]
    bitexts = bitexts.groupby(["lang", "work"]).sum().unstack().fillna(0)
    prior_work = bitexts.loc[:, "num_lines_work"].drop("Ours", axis=1)
    prior_work["Ours_public"] = bitexts.loc[:, "num_lines_pub"].sum(1)
    prior_work["Ours_all"] = bitexts.loc[:, "num_lines_all"].sum(1)
    prior_work.loc['Total'] = prior_work.sum()
    prior_work = prior_work.astype(int)
    ## GENRE TABLE. Both bitext and mono. Per language and genre.
    genre = df[["lang", "genre", "num_lines_all"]].groupby(["lang", "genre"]).sum().unstack().fillna(0)
    genre.columns = genre.columns.levels[1]
    genre = genre[["Bible", "Educational", "Legal", "Narrative", "News", "Religious", "Wikipedia", "Other/Mix"]]
    genre = genre.astype(int)
    genre.loc['Total'] = genre.sum()
    ## DATATYPE TABLE. Per language and datatype. 
    dtype = df[["lang", "datatype", "num_lines_all"]].groupby(["lang", "datatype"]).sum().unstack().fillna(0)
    dtype.columns = dtype.columns.levels[1]
    dtype = dtype[['Bitext_Previous publication', 'Bitext_Web aligned', 'Bitext_Web articles', 'Bitext_PDF aligned', 'Bitext_PDF other', 'Mono_Previous publication', 'Mono_Web', 'Mono_PDF']]
    dtype.loc['Total'] = dtype.sum()
    dtype = dtype.astype(int)
    # Save
    df.sort_values(["lang", "name"]).to_csv(output_folder / "counter.csv", index=False)
    prior_work.to_csv(output_folder / "prior_work.csv")
    genre.to_csv(output_folder / "genre.csv")
    dtype.to_csv(output_folder / "datatype.csv")

if __name__ == '__main__':
    output_folder=Path("scripts/count")
    main_prev_works = ["CreoleVal", "JHU", "LegoMT", "FLORES", "AfricaNLP-23"]
    other_works = ["LAFAND-MT", "WMT-11", "KreolMorisienMT"]
    Path(output_folder).mkdir(exist_ok=True)
    if (output_folder / "counter.csv").exists():
        counter = pd.read_csv("scripts/count/counter.csv")
    else:
        counter = count_datasets(works=main_prev_works+other_works)
    counter = classify(counter, other_works=other_works)
    save_tables(counter, output_folder)