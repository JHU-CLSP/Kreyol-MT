from clean import Clean
import glob
import os
import time
from multiprocessing import Process, Pool, current_process
import argparse
from tqdm import tqdm

class Pipeline:
    """Pipeline class for cleaning TMX files."""

    def __init__(self, dir_path, save_deleted=False, verbose=False, is_multi=True, keep_meta=False, parallel_text=False, srclang=None, tgtlang=None, srcpath=None, tgtpath=None):
        self.dir_path = dir_path
        self.save_deleted = save_deleted
        self.verbose = verbose
        self.is_multi = is_multi
        self.keep_meta = keep_meta
        self.parallel_text = parallel_text

        # Parallel Text files settings. THis only applies to a single language pair.
        if self.parallel_text:
            if srclang is None or tgtlang is None:
                print("Please provide source and target languages")
                exit()
            
            self.srclang = srclang
            self.tgtlang = tgtlang
            self.srcpath = srcpath
            self.tgtpath = tgtpath

            # change train.[src] to train.cleaned.[src] for the output files
            self.srcout = srcpath.split('.')[0] + '.cleaned.' + srcpath.split('.')[1]
            self.tgtout = tgtpath.split('.')[0] + '.cleaned.' + tgtpath.split('.')[1]

        # Whitelisted meta data. Add to this list if you would like additional meta data to be kept.
        self.whitelisted_meta = [
            'creationdate', 
            'Client:SingleString', 
            'ID:SingleString', 
            'Product Name:SingleString', 
            'Project Title:SingleString', 
            'Title:SingleString', 
            'Sensitivity Status:SinglePicklist'
            ]

        self.all_sentences = []
        self.srclang = srclang
        self.trglang = tgtlang

        # File paths for saving data
        self.cleaned_path = self.dir_path + "/cleaned/"
        self.deleted_path = self.dir_path + "/deleted/"
        self.char_path = self.dir_path + "/char_sets/"
        self.meta_path = self.dir_path + "/meta/"

    def create_nodes_from_parallel_text(self, src_path, tgt_path):
        """
        Creates the nodes from a set of parallel text files (one source file and one target file).

        Args:
            src_path (str): Path to the source file
            tgt_path (str): Path to the target file
            meta_path (str): Path to the meta data file
        
        Returns:
            nodes (list): List of nodes, where each node is a list of the source sentence, target sentence, and meta data
        """

        nodes = []

        with open(file=src_path, mode='r', encoding='utf8') as src_file, open(file=tgt_path, mode='r', encoding='utf8') as tgt_file:
            src_lines = src_file.readlines()
            tgt_lines = tgt_file.readlines()

            assert len(src_lines) == len(tgt_lines), f"Source and target files have different number of lines: {len(src_lines)} vs {len(tgt_lines)}"

            for i in range(len(src_lines)):
                meta = [] # TODO: Add support for reading in meta data

                src_line = src_lines[i].strip()
                tgt_line = tgt_lines[i].strip()

                if src_line != '' and tgt_line != '':
                    nodes.append([src_line, tgt_line, meta])
        
        return nodes


    def combine_tmx_files(self, paths):
        """
        Combines all TMX files in a directory into a list of nodes which contain the source and target sentences with meta data.

        Args:
            paths (list): List of paths to TMX files
        
        Returns:
            nodes (list): List of nodes, where each node is a list of the source sentence, target sentence, and meta data
        """
        nodes = []
        for path in paths:
            with open(file=path, mode='r', encoding='utf8') as file: # rb
                translations = [] # will cause problems if file is malformed, but significantly faster and uses way less memory
                meta = []
                cur = ''
                header_meta = []

                # Add the TMX file name to the meta data
                source_file_name = path.split('/')[-2]

                if self.is_multi:
                    lines = file.readlines()
                else:
                    lines = tqdm(file.readlines(), desc=f"Reading {path}", leave=False)

                for line in lines:
                    cur += line

                    # We don't actually use any of the header information, we just want to skip it.
                    if '<header' in cur:
                        start = cur.index('<header')
                        if '</header>' in cur:
                            end = cur.index('</header>')
                            cur = cur[end+9:]
                        elif '/>' in cur:
                            end = cur.index('/>')
                            cur = cur[end+2:]
                    else:
                        if self.srclang is None and 'xml:lang=' in cur:
                            start = cur.index('xml:lang=')
                            end = cur.index('"', start + 10)
                            self.srclang = cur[start+10:end]
                            cur = cur[start+12]
                        if self.trglang is None and 'xml:lang=' in cur:
                            start = cur.index('xml:lang=')
                            end = cur.index('"', start + 10)
                            self.trglang = cur[start+10:end]
                            cur = cur[start+12]
                        # Get creationdate and add it to meta
                        if 'creationdate' in cur:
                            start = cur.index('creationdate')
                            end = cur.index('"', start + 16)
                            creationdate = cur[start+14:end]
                            cur = cur[start+14:]
                            meta.append(['creationdate', creationdate])
                        if '</prop>' in cur:
                            # Add all meta data to meta list
                            start = cur.index('<prop type="x-') + 14
                            end = cur.index('</prop>')
                            sub = cur[start:end]
                            meta_unit = sub.split('">')
                            if meta_unit[0] in self.whitelisted_meta:
                                meta.append(meta_unit)
                            cur = cur[end+7:]
                        if '</seg>' in cur:
                            start = cur.index('<seg>')+5
                            end = cur.index('</seg>')
                            sub = cur[start:end]
                            translations.append(sub)
                            if len(translations) == 2:
                                meta.append(['source_file_name', source_file_name])
                                translations.append(meta)
                                nodes.append(translations)
                                
                                meta = []
                                translations = []
                            cur = cur[end+6:]
        return nodes

    def clean(self, nodes, save_deleted):
        """
        Cleans a list of nodes. 

        Args:
            nodes (list): List of nodes, where each node is a list of the source sentence, target sentence, and meta data
            save_deleted (bool): Whether or not to save deleted translation units
        
        Returns:
            len(nodes) (int): Number of nodes after cleaning
        """

        # Create cleaned directory if it doesn't exist
        cleaned_path = self.dir_path + "/cleaned/" 
        deleted_path = self.dir_path + "/deleted/"
        char_path = self.dir_path + "/char_sets/"
        if not os.path.exists(cleaned_path):
            os.makedirs(cleaned_path)
        if save_deleted:
            if not os.path.exists(deleted_path):
                os.makedirs(deleted_path)
            else:
                for file in os.listdir(deleted_path):
                    os.remove(deleted_path + file)
        else:
            deleted_path = None

        if not os.path.exists(char_path):
            os.makedirs(char_path)
        else:
            for file in os.listdir(char_path):
                os.remove(char_path + file)

        # Create clean object
        clean = Clean(self.srclang, self.trglang, deleted_path, char_path, self.verbose)
        
        # Clean steps
        clean_steps = [
            clean.remove_cr_and_lf,

            clean.remove_regex_patterns, # not exactly sure where to place this in the pipeline

            clean.remove_empty_segments,
            clean.normalize_html_entities,
            clean.normalize_unicode_escapes, 

            clean.remove_bad_chars,
            clean.unicode_normalization, # This step should follow remove_bad_chars
            clean.normalize_whitespace,
            clean.condense_repeated_chars,
            clean.remove_unbalanced_brackets,

            clean.remove_when_missing_alpha_chars, # (note that we have two similar functions in pipeline, this and remove_nonalpha)
            clean.remove_do_not_translate,
            clean.normalize_quotes,
            clean.remove_angle_tags,
            clean.normalize_character_set,
            clean.remove_angle_tags,
            clean.remove_tmx_tags,

            clean.remove_only_url, # we should maybe refactor this function

            clean.remove_regex_patterns, # not exactly sure where to place this in the pipeline
            clean.normalize_regex_patterns,
            clean.remove_long_words,
            
            clean.remove_empty_segments,
            clean.check_sentence_length_ratios, # This should immediately follow remove_empty_segments
                                                # in order to ensure non-zero denominators
            clean.remove_duplicates,
            clean.remove_source_equals_target,
            clean.remove_too_short,
            clean.remove_nonalpha,
            # clean.remove_too_long,

            clean.normalize_whitespace, # Need this for when there is a space before the end of a segment
            clean.remove_footnotes,

            # clean.remove_segments_with_curly_brackets,
            clean.edit_distance,
            clean.normalize_whitespace,
            clean.normalize_regex_patterns,

            clean.normalize_whitespace,
            clean.remove_empty_segments,
            clean.remove_duplicates,
        ]

        # Create a progress bar if not running in parallel
        if not self.is_multi:
            step_num = 0
            bar = tqdm(total=len(clean_steps), desc=f"Step {clean_steps[step_num].__name__}")

        # Run each step
        for step in clean_steps:
            nodes = step(nodes)
        
            # Update progress bar
            if not self.is_multi:
                step_num += 1
                if step_num < len(clean_steps):
                    if self.verbose:
                        print(f"\nStep {clean_steps[step_num].__name__} complete", flush=True)
                    bar.set_description(f"Step {clean_steps[step_num].__name__}")
                else:
                    bar.set_description(f"Cleaning Complete")
                bar.update()
        
        # Close progress bar
        if not self.is_multi:
            bar.close()

        # Write to file
        if not self.parallel_text:
            with open(file=cleaned_path + "src.txt", mode='w', encoding='utf8') as f:
                if self.verbose:
                    print(f"Writing {len(nodes)} lines to {cleaned_path}src.txt", flush=True)
                for node in nodes:
                    f.write(node[0] + "\n")

            with open(file=cleaned_path + "tgt.txt", mode='w', encoding='utf8') as f:
                if self.verbose:
                    print(f"Writing {len(nodes)} lines to {cleaned_path}tgt.txt", flush=True)
                for node in nodes:
                    f.write(node[1] + "\n")

            if self.keep_meta:
                with open(file=cleaned_path + "meta.txt", mode='w', encoding='utf8') as f:
                    if self.verbose:
                        print(f"Writing {len(nodes)} lines to {cleaned_path}meta.txt", flush=True)
                    for node in nodes:
                        f.write(str(node[2]) + "\n")

        if self.parallel_text:
            # Write out the parallel text files to self.srcout and self.tgtout
            with open(file=self.srcout, mode='w', encoding='utf8') as f:
                if self.verbose:
                    print(f"Writing {len(nodes)} lines to {self.srcout}", flush=True)
                for node in nodes:
                    f.write(node[0] + "\n")
        
            with open(file=self.tgtout, mode='w', encoding='utf8') as f:
                if self.verbose:
                    print(f"Writing {len(nodes)} lines to {self.tgtout}", flush=True)
                for node in nodes:
                    f.write(node[1] + "\n")
        
        return len(nodes)

    def run_pipeline_parallel_text(self):
        """Runs the pipeline on a single language pair of parallel text files."""

        # Create nodes from parallel text files
        nodes = self.create_nodes_from_parallel_text(self.srcpath, self.tgtpath)

        # Run the cleaning pipeline
        init_num_nodes = len(nodes)

        print(f"{self.srclang} — {self.trglang}\t\tSTART, total {init_num_nodes} lines to clean", flush=True)

        fin_num_nodes = self.clean(nodes, self.save_deleted)
        diff = init_num_nodes - fin_num_nodes

        print(f"In total, {diff} ({100 * (diff / init_num_nodes):.2f}%) lines deleted; {100 * (fin_num_nodes / init_num_nodes):.2f}% remaining", flush=True)
        print(f"\t\t\t\t\t{self.srclang}-{self.trglang} DONE, total {fin_num_nodes} clean lines", flush=True)

        # Save tuple of strings of ISO, number of starting lines, number of clean lines, number of deleted lines,
        #  percentage of clean lines, percentage of deleted lines
        stats_data = (self.srclang, self.trglang, init_num_nodes, fin_num_nodes, 
                    diff, f"{100 * (fin_num_nodes / init_num_nodes):.2f}%", f"{100 * (diff / init_num_nodes):.2f}%")
        with open("cleaning_stats.tsv", 'a') as f:
            f.write(f"{stats_data[0] + '-' + stats_data[1]:<18}\t{stats_data[2]:<14}\t{stats_data[3]:<13}\t{stats_data[4]:<15}\t{stats_data[5]:<16}\t{stats_data[6]:<18}\n")

        return 0


    def run_pipeline(self):
        """Runs the pipeline on a directory of TMX files."""

        global stats

        assert os.path.isdir(self.dir_path), f"Directory {self.dir_path} does not exist"

        # Open directory specified, get names of tmx files; look for tmx files in subdirectories also.
        paths = glob.glob(self.dir_path + "/*/*.tmx") + glob.glob(self.dir_path + "/*.tmx")

        # If no tmx files found, exit.
        if len(paths) == 0:
            print(f"No TMX files found in directory {self.dir_path}")
            exit()

        nodes = self.combine_tmx_files(paths)
        init_num_nodes = len(nodes)

        print(f"{self.srclang} — {self.trglang}\t\tSTART, total {init_num_nodes} lines to clean", flush=True)

        fin_num_nodes = self.clean(nodes, self.save_deleted)
        diff = init_num_nodes - fin_num_nodes

        print(f"In total, {diff} ({100 * (diff / init_num_nodes):.2f}%) lines deleted; {100 * (fin_num_nodes / init_num_nodes):.2f}% remaining", flush=True)
        print(f"\t\t\t\t\t{self.srclang}-{self.trglang} DONE, total {fin_num_nodes} clean lines", flush=True)

        # Save tuple of strings of ISO, number of starting lines, number of clean lines, number of deleted lines,
        #  percentage of clean lines, percentage of deleted lines
        stats_data = (self.srclang, self.trglang, init_num_nodes, fin_num_nodes, 
                    diff, f"{100 * (fin_num_nodes / init_num_nodes):.2f}%", f"{100 * (diff / init_num_nodes):.2f}%")
        with open("cleaning_stats.tsv", 'a') as f:
            f.write(f"{stats_data[0] + '-' + stats_data[1]:<18}\t{stats_data[2]:<14}\t{stats_data[3]:<13}\t{stats_data[4]:<15}\t{stats_data[5]:<16}\t{stats_data[6]:<18}\n")
        
        # Save data_info for usage in other scripts.
        with open("data_info.tsv", 'a') as f:
            f.write(f"{self.srclang}\t{self.trglang}\t{self.dir_path}\n")

        return 0

def pipe_wrapper(args):
    """Wrapper for running the pipeline in parallel."""
    return pipe(args[0], args[1], args[2], args[3], args[4])

def pipe(path, save_deleted=False, verbose=False, is_multi=True, keep_meta=False):
    """Runs the pipeline on a directory of TMX files."""
    pipeline = Pipeline(path, save_deleted, verbose, is_multi, keep_meta)
    pipeline.run_pipeline()

def parallel_text(dir_path, save_deleted=False, verbose=False, is_multi=False, keep_meta=False, parallel_text=True, srclang=None, tgtlang=None, srcpath=None, tgtpath=None):
    """Runs the pipeline on a directory of TMX files."""
    pipeline = Pipeline(
        dir_path, 
        save_deleted=save_deleted,
        verbose=verbose,
        is_multi=is_multi,
        keep_meta=keep_meta,
        parallel_text=parallel_text,
        srclang=srclang,
        tgtlang=tgtlang,
        srcpath=srcpath,
        tgtpath=tgtpath
        )
    pipeline.run_pipeline_parallel_text()


if __name__ == '__main__':
    # Parse arguments
    parser = argparse.ArgumentParser()

    # Folder directory arguments
    parser.add_argument("-m", "--multi", dest = "multi", default = None, help="Directory with multiple language pair directories")
    parser.add_argument("-s", "--single", dest = "single", default = None, help="Directory with tmx files of single language pair", nargs="+")

    # Parallel text arguments
    parser.add_argument("-t", "--parallel_text", dest="parallel_text", default=False, help="Directory for saving cleaned parallel text")
    parser.add_argument("-srclang", "--source_language", dest="srclang", default=None, help="Source language for parallel text")
    parser.add_argument("-tgtlang", "--target_language", dest="tgtlang", default=None, help="Target language for parallel text")
    parser.add_argument("-srcpath", "--source_path", dest="srcpath", default=None, help="Path to source file for parallel text")
    parser.add_argument("-tgtpath", "--target_path", dest="tgtpath", default=None, help="Path to target file for parallel text")

    # Other arguments
    parser.add_argument("-p", "--processes",dest ="processes", default = 1, help="Number of processes to use (Max 8)")
    parser.add_argument("-d", "--save_deleted", dest="save_deleted", action=argparse.BooleanOptionalAction, default=False, help="Whether or not to save deleted translation units")
    parser.add_argument("-v", "--verbose", dest="verbose", action=argparse.BooleanOptionalAction, default=False, help="Print more extensive information when cleaning")
    parser.add_argument("--meta", dest= "keep_meta", default=False, action=argparse.BooleanOptionalAction, help="Whether or not to keep meta data (default: False)")

    args = parser.parse_args()

    if args.single is None and args.multi is None and args.parallel_text is None:
        print(f"Please provide a directory. Use -h for help")
        exit()
    elif args.single is not None and args.multi is not None or args.single is not None and args.parallel_text is not None or args.multi is not None and args.parallel_text is not None:
        print(f"Please only use -m or -s, but not both.")
        exit()

    if int(args.processes) < 1 or int(args.processes) > 24:
        print("Please provide a valid number of processes (Max 24)")
        exit()

    if args.single is not None:
        paths = args.single
    elif args.multi is not None:
        paths = glob.glob(args.multi + "/*/", recursive=True)
    elif args.parallel_text is not None:
        start = time.time()
        parallel_text(args.parallel_text, args.save_deleted, args.verbose, False, args.keep_meta, args.parallel_text, args.srclang, args.tgtlang, args.srcpath, args.tgtpath)
        end = time.time()

        hours, rem = divmod(end-start, 3600)
        minutes, seconds = divmod(rem, 60)

        print("\nCompleted Cleaning")
        print("\nTotal time: {:0>2}:{:0>2}:{:05.2f}\n\n".format(int(hours),int(minutes),seconds))
        exit()

    # Initialize the statistics to be collected
    global stats
    stats = []

    # Print the paths to be cleaned
    print(f"Cleaning {len(paths)} language pair(s):")
    [print(path) for path in paths]

    if args.keep_meta:
        print("\nMaintaining meta data in meta.txt files")

    start = time.time()

    print("\nBeginning Cleaning\n")

    with open(file="cleaning_stats.tsv", mode='a', encoding='utf8') as f:
        f.write(f"{'ISO':<18}\t{'Starting Lines':<14}\t{'Clean Lines':<13}\t{'Deleted Lines':<15}\t{'Percentage Clean':<16}\t{'Percentage Deleted':<18}\n")
    with open(file="data_info.tsv", mode='a', encoding='utf8') as f:
        f.write(f"{'Source'}\t{'Target'}\t{'Directory'}\n")

    # Run the pipeline either in parallel or sequentially
    if int(args.processes) == 1:
        for path in paths:
            pipe(path, args.save_deleted, args.verbose, is_multi=False, keep_meta=args.keep_meta)
    else:
        print("keep_meta", args.keep_meta)
        multi_args = [(path, args.save_deleted, args.verbose, True, args.keep_meta) for path in paths]

        with Pool(processes=int(args.processes)) as pool:
            pool.map(pipe_wrapper, multi_args)

    end = time.time()

    hours, rem = divmod(end-start, 3600)
    minutes, seconds = divmod(rem, 60)

    print("\nCompleted Cleaning")
    print("\nTotal time: {:0>2}:{:0>2}:{:05.2f}\n\n".format(int(hours),int(minutes),seconds))
