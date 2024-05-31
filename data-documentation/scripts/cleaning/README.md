# Data Cleaning Pipeline

Cleaning the data:

1.  Use the `gen_datasets.py` script to generate the combined train, dev, and test files per language pair.
2.  Make sure you're in this directory (`CreoleMTData/scripts/cleaning/`)
3.  Run clean_all.py:

```
python clean_all.py data_output_path/ cleaning_info_out_path/ --clean_train True
```

The `data_output_path` should be a path to the folder that contains the data output by the `gen_datasets.py` script. the `cleaning_info_out_path` is a path to a new folder that will output all of the cleaned data and the data that is removed by cleaning. It will be formatted in the same way as `data_output_path` but it will contain a deleted folder which contains which source and target files are deleted and also a metadata file that shows what cleaning step removed the particular line.

**The cleaned data will be named `train.cleaned.[src]`, `dev.cleaned.[tgt]`, etc. It will not overwrite the original `train.[src]` or `train.[tgt]` files. The cleaned data will be contained in the `data_output_path`.**

Keep in mind that when you are cleaning dev, test, and train datasets, the train information will be what is output into the `cleaning_info_out_path` directory, while the dev and test info will have been overwritten.

For ease, `run_clean_all.sh` has been included so that it is easy to run one file to generate the datasets and then clean them.

For more details on running the cleaning script for one language pair, see the `README.md` file in `data-cleaning-pipeline/README.md`.

