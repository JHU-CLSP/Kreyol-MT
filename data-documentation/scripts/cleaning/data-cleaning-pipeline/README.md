# Data Cleaning Pipeline
Data cleaning pipeline framework and cleaning steps.

# Command-line Usage

## Single Language Pair, Parallel Text Files (NOT TMX)
In this example, we have the `-d` and `-v` flags for saving the deleted lines (for viewing) and outputting verbosely. Make sure the `-t` flag is set when using parallel text files instead of TMX files. Also, the srclang and tgtlang flags need to match config file names in order to have language-specific parameters from the config files. If a language config doesn't exist, make a new config file and name it the same thing you put in the `-tgtlang` or `-srclang` flag.

I recommend using a bash script with variables so that the command doesn't get too long with all of the different parameters:
```
SAVE_DIR=../data-cleaning/en_km_test
SRC_LANG=en-US
TGT_LANG=km-KH
SRC_FILE=../data-cleaning/en_km_test/ParaCrawl.en-km.en
TGT_FILE=../data-cleaning/en_km_test/ParaCrawl.en-km.km

python3 pipeline.py -t $SAVE_DIR -srclang $SRC_LANG -tgtlang $TGT_LANG -srcpath $SRC_FILE -tgtpath $TGT_FILE -d -v
```

**There is currently no support for multiprocessing for parallel text file input. You can only clean one pair at a time.**

## Single Directory, One Language Pair (TMX)

Make sure you use `-s` before the specified single directory.
```
python3 pipeline.py -s data/Cambodian/
```
```
python3 pipeline.py --single data/Cambodian
```

If you want to clean multiple specific directories (i.e. not all the directories in a parent directory) you can chain the paths like this:
```
python3 pipeline.py -s data/Cambodian data/French data/Spanish
```
<br>

## Directory Containing Multiple Sub-Directories (One Language Pair per Sub-Directory, TMX)
These subdirectories can contain more directories if they contain TMX files. It can also be sub-directories full of TMX files.

```
python3 pipeline.py -m data/ -p 5
```
```
python3 pipeline.py --multi data/ --processes 5
```

## Save Deleted TUs
Use `-d` to collect all TUs that are deleted during cleaning and save them to files.
```
python3 pipeline.py -d -s data/Cambodian
```
```
python3 pipeline.py --save_deleted -s data/Cambodian
```

<br>

## Verbosely print additional information
Use `-v` to print additional information about how many TUs are being removed at each step.
```
python3 pipeline.py -v -s data/Cambodian
```
```
python3 pipeline.py --verbose -s data/Cambodian
```

<br>

## Argument details found using `--help` or `-h`:
```
usage: pipeline.py [-h] [-m MULTI] [-s SINGLE [SINGLE ...]] [-t PARALLEL_TEXT] [-srclang SRCLANG] [-tgtlang TGTLANG] [-srcpath SRCPATH] [-tgtpath TGTPATH]
                   [-p PROCESSES] [-d | --save_deleted | --no-save_deleted] [-v | --verbose | --no-verbose] [--meta | --no-meta]

options:
  -h, --help            show this help message and exit
  -m MULTI, --multi MULTI
                        Directory with multiple language pair directories
  -s SINGLE [SINGLE ...], --single SINGLE [SINGLE ...]
                        Directory with tmx files of single language pair
  -t PARALLEL_TEXT, --parallel_text PARALLEL_TEXT
                        Directory for saving cleaned parallel text
  -srclang SRCLANG, --source_language SRCLANG
                        Source language for parallel text
  -tgtlang TGTLANG, --target_language TGTLANG
                        Target language for parallel text
  -srcpath SRCPATH, --source_path SRCPATH
                        Path to source file for parallel text
  -tgtpath TGTPATH, --target_path TGTPATH
                        Path to target file for parallel text
  -p PROCESSES, --processes PROCESSES
                        Number of processes to use (Max 8)
  -d, --save_deleted, --no-save_deleted
                        Whether or not to save deleted translation units
  -v, --verbose, --no-verbose
                        Print more extensive information when cleaning
  --meta, --no-meta     Whether or not to keep meta data (default: False)
```
