from collections import defaultdict
import math
import pathlib
import random
import shutil
from typing import Collection, Iterable, Sequence, TypedDict
import click
import frontmatter


def is_public(corpus_dir: pathlib.Path) -> bool:
    readme_path = corpus_dir / "README.md"
    if not readme_path.exists():
        return False
    md = frontmatter.load(readme_path)
    release = md.get("release")
    return release == "public"


class SplitDataset(TypedDict):
    dev: Sequence[tuple[str, str]]
    test: Sequence[tuple[str, str]]
    train: Sequence[tuple[str, str]]


def get_split(
    creole_test_sents: Collection[str],
    lexifier_test_sents: Collection[str],
    max_sents: int,
    min_sents: int,
    pair_sents: Iterable[tuple[str, str]],
    test_ratio: float,
    train_ratio: float,
) -> tuple[SplitDataset, list[tuple[str, str]]]:
    filtered_sents: list[tuple[str, str]] = []
    skipped: list[tuple[str, str]] = []
    for creole_sent, lexifier_sent in pair_sents:
        if creole_sent in creole_test_sents or lexifier_sent in lexifier_test_sents:
            # Should we put them in the test set instead?
            skipped.append((creole_sent, lexifier_sent))
        else:
            filtered_sents.append((creole_sent, lexifier_sent))

    dedup_sents = list(set(filtered_sents))
    random.shuffle(dedup_sents)
    test_cutoff = max(
        min_sents,
        min(max_sents, math.ceil(len(dedup_sents) * test_ratio)),
    )
    dev_cutoff = test_cutoff + max(
        min_sents,
        min(max_sents, math.ceil(len(dedup_sents) * (1 - train_ratio - test_ratio))),
    )
    if dev_cutoff > len(dedup_sents):
        splits = {
            "dev": [],
            "test": [],
            "train": dedup_sents,
        }
    else:
        splits = {
            "dev": dedup_sents[test_cutoff:dev_cutoff],
            "test": dedup_sents[:test_cutoff],
            "train": dedup_sents[dev_cutoff:],
        }
    return splits, skipped


def get_flores_en_path(
    data_dir: pathlib.Path, split: str
) -> tuple[pathlib.Path, pathlib.Path]:
    res = data_dir / "eng" / "mono" / "raw" / "FLORES-200" / f"{split}.eng"
    if not res.exists():
        raise FileNotFoundError(f"FLORES eng is missing at {res}")
    return res


@click.command(
    help="Generate per-lang train/dev datasets and filter out test sentences from them."
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
    "--min-sents",
    default=50,
    help="The minimum number of sentences in a dev or test split.",
    type=click.IntRange(0),
)
@click.option(
    "--max-sents",
    default=1024,
    help="The maximum number of sentences in a dev or test split.",
    type=click.IntRange(0),
)
@click.option(
    "--public",
    "public_only",
    help="Only use publicly available corpora",
    is_flag=True,
)
@click.option(
    "--test-ratio",
    default=0.1,
    help="The fraction of the overall datasets to use in the output test.",
    type=click.FloatRange(0.0, 1.1),
)
@click.option(
    "--train-ratio",
    default=0.85,
    help="The fraction of the overall datasets to use in the output train.",
    type=click.FloatRange(0.0, 1.1),
)
@click.option(
    "--seed",
    default=135,
    help="The random seed to use for train/dev splitting.",
    type=int,
)
def main(
    data_dir: pathlib.Path,
    max_sents: int,
    min_sents: int,
    output_dir: pathlib.Path,
    public_only: bool,
    seed: int,
    test_ratio: float,
    train_ratio: float,
):
    random.seed(seed)

    # ALL test files, not only those in bitext dirs, so we also catch FLORES english
    test_files = [
        f for f in data_dir.glob("**/test.*") if not public_only or is_public(f.parent)
    ]

    # If lookups ever becomes too slow, we can use:
    # - Tries
    # But tbh we ain't gonna need it.
    test_sents: defaultdict[str, set[str]] = defaultdict(set)
    for creole_file in test_files:
        with creole_file.open() as in_stream:
            test_sents[creole_file.suffix[1:]].update(s.strip() for s in in_stream)

    # Read data
    lang_pair_dirs = data_dir.glob("**/bitexts/*--*")
    lang_pairs: set[tuple[str, str]] = {
        tuple(d.name.split("--")) for d in lang_pair_dirs
    }
    all_sents: defaultdict[tuple[str, str], list[tuple[str, str]]] = defaultdict(list)
    for creole, lexifier in lang_pairs:
        for split in ("dev", "train", "traindev"):
            for creole_file in data_dir.glob(
                f"**/bitexts/{creole}--{lexifier}/**/{split}.{creole}"
            ):
                # Avoid loops
                if output_dir in creole_file.parents:
                    continue
                if public_only and not is_public(creole_file.parent):
                    print(f"Skipping non-public corpus {creole_file}")
                    continue
                lexifier_file = creole_file.with_suffix(f".{lexifier}")
                if not lexifier_file.exists():
                    # Special case for FLORES: look for the English in its special
                    # dir. Not very robust but it should be ok for now
                    if creole_file.parent.name == "FLORES-200":
                        lexifier_file = get_flores_en_path(
                            data_dir, split=creole_file.stem
                        )
                    else:
                        click.echo(f"Missing file: {lexifier_file}")
                        continue
                with (
                    creole_file.open() as creole_in,
                    lexifier_file.open() as lexifier_in,
                ):
                    for creole_sent, lexifier_sent in zip(
                        creole_in, lexifier_in, strict=True
                    ):
                        cr = creole_sent.strip()
                        lx = lexifier_sent.strip()
                        if cr and lx:
                            all_sents[(creole, lexifier)].append((cr, lx))

    all_splits: dict[tuple[str, str], SplitDataset] = dict()
    extra_test_sents: defaultdict[str, set[str]] = defaultdict(set)
    skipped_count = 0
    duplicate_count = 0
    # Filter, dedup, split
    for (creole, lexifier), pair_sents in all_sents.items():
        pair_output_dir = output_dir / f"{creole}--{lexifier}"
        splits, skipped = get_split(
            creole_test_sents=test_sents[creole],
            lexifier_test_sents=test_sents[lexifier],
            max_sents=max_sents,
            min_sents=min_sents,
            pair_sents=pair_sents,
            test_ratio=test_ratio,
            train_ratio=train_ratio,
        )
        if dedup_delta := (
            len(pair_sents) - sum(len(s) for s in splits.values()) - len(skipped)
        ):
            click.echo(
                f"Removed {dedup_delta} duplicate pairs for {creole}--{lexifier}"
                f" ({dedup_delta/len(pair_sents):.2%})"
            )
            duplicate_count += dedup_delta
        if skipped:
            # This is redundant but avoids creating empty dirs
            pair_output_dir.mkdir(exist_ok=True, parents=True)
            with open(pair_output_dir / "skipped.txt", "w") as skipped_out:
                for creole_sent, lexifier_sent in skipped:
                    skipped_out.write(f"{creole_sent} ||| {lexifier_sent}\n")
                    skipped_count += 1
            click.echo(
                f"Skipped {len(skipped)} spilling pairs for {creole}--{lexifier}"
                f" ({len(skipped)/len(pair_sents):.2%})"
            )
        all_splits[(creole, lexifier)] = splits
        extra_test_sents[creole].update(
            creole_sent for creole_sent, _ in splits["test"]
        )
        extra_test_sents[lexifier].update(
            lexifier_sent for _, lexifier_sent in splits["test"]
        )
    click.echo(
        f"Removed a total of {duplicate_count} duplicated pairs for all langs"
        f" ({duplicate_count/sum(len(v) for v in all_sents.values()):.2%})"
    )
    click.echo(
        f"Skipped a total of {skipped_count} spilling pairs for all langs"
        f" ({skipped_count/sum(len(v) for v in all_sents.values()):.2%})"
    )
    del all_sents, test_sents, skipped
    # Avoid spillage in our generated test sets
    # Deactivated for now because it burns too much of our train/dev sets in small langs
    # for (creole, lexifier), splits in all_splits.items():
    #     for s in ("train", "dev"):
    #         filtered = [
    #             (cr, lx)
    #             for cr, lx in splits[s]
    #             if cr not in extra_test_sents[creole]
    #             and lx not in extra_test_sents[lexifier]
    #         ]
    #         if len(filtered) < (unf_s := len(splits[s])):
    #             click.echo(
    #                 f"Removed {unf_s-len(filtered)} spilling sentences"
    #                 f" in {creole}--{lexifier} {s} from {unf_s}"
    #                 f" ({(unf_s-len(filtered))/unf_s:.2%})"
    #             )
    #         splits[s] = filtered

    idx = 1
    tot_num = len(all_splits)
    print("first loop...")
    for (creole, lexifier), split in all_splits.items():
        print(f"{idx}/{tot_num} ({creole}-{lexifier})", end=' ', flush=True)
        idx += 1
        for split_name, s in split.items():
            pair_output_dir = output_dir / f"{creole}--{lexifier}"
            if s:
                # This is redundant but avoids creating empty dirs
                pair_output_dir.mkdir(exist_ok=True, parents=True)
                with (
                    open(pair_output_dir / f"{split_name}.{creole}", "w") as creole_out,
                    open(
                        pair_output_dir / f"{split_name}.{lexifier}", "w"
                    ) as lexifier_out,
                ):
                    for creole_sent, lexifier_sent in s:
                        creole_out.write(f"{creole_sent}\n")
                        lexifier_out.write(f"{lexifier_sent}\n")
            else:
                print()
                click.echo(f"No generated {split_name} set for {creole}--{lexifier}")
    print()

    # Existing test sets
    idx = 1
    tot_num = len(lang_pairs)
    print("second loop...")
    for creole, lexifier in lang_pairs:
        # print statement
        print(f"{idx}/{tot_num} ({creole}-{lexifier})", end=' ', flush=True)
        idx += 1
        # actual work
        pair_output_dir = output_dir / f"{creole}--{lexifier}"
        for creole_file in data_dir.glob(
            f"**/bitexts/{creole}--{lexifier}/**/test.{creole}"
        ):
            lexifier_file = creole_file.with_suffix(f".{lexifier}")
            if public_only and not is_public(creole_file.parent):
                print()
                print(f"Skipping non-public corpus {creole_file}")
                continue
            if not lexifier_file.exists():
                if creole_file.parent.name == "FLORES-200":
                    lexifier_file = lexifier_file = get_flores_en_path(
                        data_dir, split=creole_file.stem
                    )
                else:
                    print()
                    click.echo(f"Missing file: {lexifier_file}")
                    continue
            # This is redundant but avoids creating empty dirs
            pair_output_dir.mkdir(exist_ok=True, parents=True)
            shutil.copy(
                creole_file,
                pair_output_dir / f"{creole_file.parent.name}-test.{creole}",
            )
            shutil.copy(
                lexifier_file,
                pair_output_dir / f"{creole_file.parent.name}-test.{lexifier}",
            )
    print()


if __name__ == "__main__":
    main()
