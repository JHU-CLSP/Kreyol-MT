from cgitb import text
import re
import os
import html
import yaml
import statistics
import unicodedata
import editdistance

from tqdm import tqdm
from os.path import exists, join
from collections import Counter
from bisect import bisect

def _load_config_file(lang):
    """
    Loads the config file for the given language.
    If it does not exist, pulls data from the default config file.

    Args:
        lang the language of the config file to load
    
    Returns:
        a dictionary of configuration values
    """
    config_path = f'config/{lang}.yaml'
    if exists(config_path):
        with open(config_path, mode='r', encoding='utf8') as file:
            config = yaml.load(file, Loader=yaml.FullLoader)
        print(f'Loaded config for {lang}')
    else:
        config = {}
    return config

def _load_config(lang):
    """
    Loads the config file for the given langauge.
    Converts data types for efficiency.

    Args:
        lang (string): the language of the config file to load
    
    Returns:
        a dictionary of configuration values
    """
    config = _load_config_file(lang)
    if 'allowed_spaces' in config:
        config['allowed_spaces'] = set(config['allowed_spaces'])
    if 'allowed_quotes' in config:
        config['allowed_quotes'] = set(config['allowed_quotes'])
    if 'allowed_single_quotes' in config: 
        config['allowed_single_quotes'] = set(config['allowed_single_quotes'])
        
    if 'normalize_characters' in config:
        char_dict = config['normalize_characters']
        for k,v in list(char_dict.items()):
            del char_dict[k]
            char_dict[chr(int(k))] = ''.join(map(lambda c: chr(int(c)), v.split(','))) if v else ''
        if lang!='default':
            for k, v in default_config['normalize_characters'].items():
                if k not in char_dict:
                    char_dict[k] = v
        
    
    if 'allowed_characters' in config:
        char_list = []
        for k in config['allowed_characters']:
            parts = list(map(lambda x: int(x), k.split('-')))
            if len(parts) == 1:
                char_list.append(chr(parts[0]))
            else:
                for c in range(parts[0], parts[1]+1):
                    char_list.append(chr(c))
        config['allowed_characters'] = set(char_list)

    # if 'normalize_regex_patterns' in config:
    #     pattern_dict = config['normalize_regex_patterns']
    #     if pattern_dict is not None:
    #         if lang!='default':
    #             for k, v in default_config['normalize_regex_patterns'].items():
    #                 if k not in pattern_dict:
    #                     pattern_dict[k] = v
    #     else:
    #         pattern_dict = {}

    #     config['normalize_regex_patterns'] = pattern_dict
        

    if lang != 'default':
        for key in default_config:
            if key not in config:
                config[key] = default_config[key]
    return config

default_config = _load_config('default')

blocks_left = []
blocks_right = []
with open('config/unicode-blocks.txt', 'r') as file:
    for line in file:
        left, right = tuple(map(int, line.split()[:2]))
        blocks_left.append(left)
        blocks_right.append(right)

class Clean:
    # Add data members here
    def __init__(self, src, trg, deleted_dir=None, char_dir=None, verbose=False):
        self.srclang = src
        self.trglang = trg

        self.deleted_dir = deleted_dir
        self.char_dir = char_dir
        self.verbose = verbose

        self.all_whitespace = self._load_whitespace()
        self.all_quotations = self._load_quotations() 
        self.single_quotations = self._load_single_quotations() 

        self.src_params = _load_config(src)
        self.tgt_params = _load_config(trg)

    def _load_whitespace(self):
        """
        Loads the config file for all whitespace.
        
        Args:
            A set of all whitespace values.
        """
        whitespace = set()
        with open('config/all_whitespace.txt', 'r') as file:
            for line in file:
                whitespace.add(chr(int(line.split()[0], 16)))
        return whitespace
    
    def _load_quotations(self):
        """ Loads the config file for all quotation.
        Args:
            A set of all quotations values.
        """
        quotations = set()
        with open('config/all_quotation.txt', mode='r', encoding='utf8') as file:
            for line in file:
                quotations.add(chr(int(line.split()[0], 16)))
        return quotations
    
    def delete_indices(self, nodes, remove, step):
        """
        Delete specified indexes from list in O(n) time.

        Args:
            nodes (list of tmx nodes): tmxobject the source and target language nodes
            remove: ordered list of indices to remove
        Returns:
            list of tmx nodes: Updated tmx object
        """
        if self.deleted_dir:
            with open(os.path.join(self.deleted_dir, 'deleted_src.txt'), mode='a', encoding='utf8') as d_src, \
                    open(os.path.join(self.deleted_dir, 'deleted_tgt.txt'), mode='a', encoding='utf8') as d_tgt, \
                        open(os.path.join(self.deleted_dir, 'deleted_meta.txt'), mode='a', encoding='utf8') as d_meta:
                
                if self.verbose:
                    print(f"\nRemoving {len(remove)} units")
                for i in remove:
                    try:
                        d_src.write(nodes[i][0] + "\n")
                        d_tgt.write(nodes[i][1] + "\n")
                    # If there is an error, print the error and the node
                    except Exception as e:
                        print(f"Error: {e}")
                        print(f"Node: {nodes[i]}")
                        exit(1)
                    
                    new_meta = nodes[i][2].copy()
                    new_meta.append(step)
                    d_meta.write(str(new_meta) + "\n")

        i,j = 0, 0
        for k in range(len(nodes)):
            if j < len(remove) and k==remove[j]: # If we are at an index to remove
                j += 1
            else:
                nodes[i] = nodes[k] # Move the node to the front
                i += 1
        return nodes[:i]

    def _load_single_quotations(self):
        """ Loads the config file for all quotation.
        Args:
            A set of all quotations values.
        """
        single_quotations = set()
        with open('config/single_quotation.txt', mode='r', encoding='utf-8') as file:
            for line in file:
                single_quotations.add(chr(int(line.split()[0], 16)))
        return single_quotations 

    def remove_cr_and_lf(self, nodes):
        """
        Detect and fix technical issues in the content
            (\r) or (\n) in hex we have (&#xd)
        Args:
            nodes (list): list of lists of source and target strings
        Returns:
            list: nodes with fixed CR/LF issues
        """
        src_match_pattern = re.compile(self.src_params['cr_and_lf_match_pattern'])
        tgt_match_pattern = re.compile(self.tgt_params['cr_and_lf_match_pattern'])

        for node in nodes:
            node[0] = re.sub(src_match_pattern, self.src_params['cr_and_lf_replace_pattern'], node[0]) # node[0] is src
            node[1] = re.sub(tgt_match_pattern, self.tgt_params['cr_and_lf_replace_pattern'], node[1]) # node[1] is tgt

        return nodes
    
    def remove_empty_segments(self, nodes):
        """
        Remove nodes where either the source or target is empty
        
        Args:
            nodes (list): list of lists of source and target strings
        Returns:
            list: subset of nodes where neither source nor target is empty
        """
        if self.verbose:
            old_len = len(nodes)
            nodes = [node for node in nodes if node[0] and node[1]]
            print(f"\nRemoving {old_len - len(nodes)} empty segments")
            return nodes
        return [node for node in nodes if node[0] and node[1]]

    def remove_tmx_tags(self, nodes):
        pattern = r"org\.ldschurch\.psd\.mt\.tmx\. ?(Ph|Bpt|Ept)@[\da-fA-F]+"
        pattern = re.compile(pattern)
        
        for node in nodes:
            node[0] = re.sub(pattern, "", node[0])
            node[1] = re.sub(pattern, "", node[1])

        return nodes

        
    def remove_angle_tags(self, nodes):
        """
        Removes angle brackets. Including those that do not close. 

        Args:
            nodes (list): list of lists of source and target strings
        Returns:
            list: Updated nodes without angle brackets
        """
        # Remove double tags (i.e. <tag1><tag2> -> <tag>)
        double_tag_pattern = re.compile(r"(<[^>]*?>){2,}")
        tag_pattern_with_number = re.compile(r"(<[^>]*?>){1,}(?=[\d\W])")
        for node in nodes:
            # TODO: replace double tags with <tag> unless there is a number \d\d after the tag
            if re.search(double_tag_pattern, node[0]):
                node[0] = re.sub(tag_pattern_with_number, "<tag>", node[0])
                node[0] = re.sub(double_tag_pattern, "<tag> ", node[0])
            if re.search(double_tag_pattern, node[1]):
                node[1] = re.sub(tag_pattern_with_number, "<tag>", node[1])
                node[1] = re.sub(double_tag_pattern, "<tag> ", node[1])
            # node[0] = re.sub(double_tag_pattern, " <tag>", node[0])
            # node[1] = re.sub(double_tag_pattern, " <tag>", node[1])
            

        for node in nodes: 
            node[0] = re.sub(r'<+(.*?)>+', "", node[0])
            node[0] = re.sub(r'<+!*-*', "", node[0])

            node[1] = re.sub(r'<+(.*?)>+', "", node[1])
            node[1] = re.sub(r'<+!*-*', "", node[1])
        return nodes

    def _normalize_whitespace_helper(self, sent, allowed, replace):
        """
        Normalizes whitespace in a sentence.

        Whitespace values that are not allowed are replaced with a default value.
        Several whitespaces are combined to the first value.

        Args:
            sent (string): the sentence to be normalized
            allowed (set of strings): the allowed whitespaces for this language
            replace (string): the default whitespace for this language

        Returns:
            string: the normalized whitespace
        """
        normalized_whitespace = []
        state = True
        for c in sent:
            if c in self.all_whitespace:
                if state:
                    if c not in allowed:
                        c = replace
                    normalized_whitespace.append(c)
                    state = False
            else:
                state = True
                normalized_whitespace.append(c)
        normalized_whitespace = ''.join(normalized_whitespace).strip()
        return normalized_whitespace

    def normalize_whitespace(self, nodes):
        """
        Normalize whitespace to values specified in a config file.

        Args:
            nodes (list): list of lists of source and target strings
        Returns:
            list: Updated nodes with normalized whitespace
        """
        src_allowed = self.src_params['allowed_spaces']
        src_replace = self.src_params['replacement_space']
        targ_allowed = self.tgt_params['allowed_spaces']
        targ_replace = self.tgt_params['replacement_space']
        for i, (s, t, m) in enumerate(nodes):
            s = self._normalize_whitespace_helper(s, src_allowed, src_replace)
            t = self._normalize_whitespace_helper(t, targ_allowed, targ_replace)
            nodes[i] = [s, t, m]

        # Remove the whitespace at the beginning and end of the sentence
        for i, (s, t, m) in enumerate(nodes):
            s = s.strip()
            t = t.strip()
            nodes[i] = [s, t, m]
            
        return nodes
    
    def _normalize_single_quotes_helper(self, sent, allowed, replace):
        """ Normalize single quotees in a sentence. 

        Args:
            sent (string): the sentence to be normalized 
            allowed (set of strings):the allowed single quotations for this language
            replace (set of strings):the replace single quotations for this language
        
        Returns: 
            string: the normalized quotations 
        """
        normalized_single_quotes = []
        for c in sent:
            if c in self.single_quotations and c not in allowed:
                c = list(replace)[0]
            normalized_single_quotes.append(c)
        single_norm = ''.join(normalized_single_quotes)
        return single_norm
   
    def _normalize_quotes_helper(self, sent, allowed, replace):
        """ 
        Normalizes quotes in a sentence.
        If we have an odd number of quotation marks we remove them completely from the sentence. 
        Quotation marks that are not allowed are replaced with a default value.

        Args:
            sent (string): the sentence to be normalized
            allowed (set of strings): the allowed quotations for this language
            replace (set of strings): the default quotations for this language

        Returns:
            string: the normalized quotations 
        """
        quote_count = sum([1 for c in sent if c in self.all_quotations])
        normalized_quotes = []
        if quote_count % 2 != 0: # Odd 
            normalized_quotes = [c for c in sent if c not in self.all_quotations]
        else:
            for c in sent:
                if c in self.all_quotations and c != allowed:
                    c = list(replace)[0]
                normalized_quotes.append(c)
        norm_str = ''.join(normalized_quotes)
        return norm_str
    
    def normalize_quotes(self, nodes):
        """ 
        Normalize quotations to values specified in config file. 
        1. Odd number of quotes: remove all quotees
        2. Even number of quotes: normalize to 1 type of quotes 
        Note: Does not clean single quotes because they might mess up apostrophes

        Args:
            nodes (list): list of lists of source and target strings
        Returns: 
            list: Updated nodes with normalized quotes 
        """

        if not self.src_params['normalize_quotes'] or not self.tgt_params['normalize_quotes']:
            if self.verbose:
                print('\nNormalizing quotes is disabled')
            return nodes

        src_single_allowed = self.src_params['allowed_single_quotes']
        src_single_replace = self.src_params['replacement_single_quotes']

        targ_single_allowed = self.tgt_params['allowed_single_quotes']
        targ_single_replace = self.tgt_params['replacement_single_quotes']

        src_allowed = self.src_params['allowed_quotes']
        src_replace = self.src_params['replacement_quotes']

        targ_allowed = self.tgt_params['allowed_quotes']
        targ_replace = self.tgt_params['replacement_quotes']

        for i, (s, t, m) in enumerate(nodes): 
            # # single quotes normalization 
            s = self._normalize_single_quotes_helper(s, src_single_allowed, src_single_replace)
            t = self._normalize_single_quotes_helper(t, targ_single_allowed, targ_single_replace)
            
            # normalize double quotes and angle quotes 
            s = self._normalize_quotes_helper(s, src_allowed, src_replace)
            t = self._normalize_quotes_helper(t, targ_allowed, targ_replace)

            nodes[i] = [s, t, m]
        return nodes

    def normalize_html_entities(self, nodes):
        """
        Replace HTML entities with their unicode equivalent 

        Args:
            nodes (list): list of lists of source and target strings
        Returns:
            list: the same list with HTML entities replaced with their unicode equivalent
        """
        for node in nodes:
            # Un-escape source
            m = html.unescape(node[0])
            while node[0] != m:
                node[0] = m
                m = html.unescape(node[0])

            # Un-escape target
            m = html.unescape(node[1])
            while node[1] != m:
                node[1] = m
                m = html.unescape(node[1])

        return nodes

    def normalize_unicode_escapes(self, nodes):
        """
        Checks for specific unicode code points and replaces them with their values. Currently
        rather slow, but works for everything except for Russian source: individual\u0027s"

        Args:
            nodes (list): list of lists of source and target strings

        Returns:
            list: the same list with HTML entities replaced with their unicode equivalent
        """
        p_src = re.compile(self.src_params['unicode_escape_pattern']) # Default matches unicode code points of the form \uXXXX
        p_tgt = re.compile(self.tgt_params['unicode_escape_pattern']) # Default matches unicode code points of the form \uXXXX
        for node in nodes:
            m = re.search(p_src, node[0])
            if m:
                # The lambda function replaces extracts the hexadecimal value of the code point,
                # converts it to an integer, and then converts it to a character
                node[0] = re.sub(p_src, lambda m: chr(int(m.group(1), 16)), node[0])
            
            m = re.search(p_tgt, node[1])
            if m:
                # Same lambda function as above
                node[1] = re.sub(p_tgt, lambda m: chr(int(m.group(1), 16)), node[1])
        return nodes

    def unicode_normalization(self, nodes):
        """
        Applies a standardized type of unicode normalization, as described here:
        https://docs.python.org/3/library/unicodedata.html#unicodedata.normalize 
        or
        https://towardsdatascience.com/difference-between-nfd-nfc-nfkd-and-nfkc-explained-with-python-code-e2631f96ae6c
        By default, we use NFKC normalization, i.e., a compatibility decomposition followed by a canonical
        composition - but perhaps we should parameterize this in the future.
        Args:
            nodes (list): list of lists of source and target strings

        Returns:
            list: the same list with strings normalized 
        """
        for node in nodes:
            # NFKC is the default normalization form
            node[0] = unicodedata.normalize(self.src_params['unicode_normalization_mode'], node[0]) 
            node[1] = unicodedata.normalize(self.tgt_params['unicode_normalization_mode'], node[1])
        return nodes

    def remove_bad_chars(self, nodes):
        """
        Remove escape slashes from the source and target strings
        Args:
            nodes (list): list of lists of source and target strings
        Returns:
            list: the same list with escape slashes removed"""
        bad_chars = self.src_params['specific_chars_to_remove']
        for c in bad_chars:
            for n in nodes:
                n[0] = n[0].replace(c, '')
                n[1] = n[1].replace(c, '')
        return nodes

    def remove_source_equals_target(self, nodes):
        """
        Checks for instances where the source sentence is identical to the target sentence.
        The source and target sentences will be set to lowercase and then will be 
        stripped of punctuation and spaces. If an identical instance is found, it will 
        remove both the source and target.
        Args:
            nodes (list): list of lists of source and target strings

        Returns:
            the list of nodes without the nodes with identical translations
        """
        bad = []
        for i in range(len(nodes)):
            src_stripped = ''.join([i for i in nodes[i][0].lower() if i.isalpha()])
            tgt_stripped = ''.join([i for i in nodes[i][1].lower() if i.isalpha()])
            if src_stripped == tgt_stripped:
                bad.append(i)

        return self.delete_indices(nodes, bad, 'remove_source_equals_target')

    def remove_fuzzy_duplicates(self, nodes):
        """
        Removes all fuzzy duplicate instances of source and target. Two parallel sentences are 
        considered a fuzzy duplicate when all of the alphabetical characters from both the source 
        and the target of one parallel data instance are exactly the same as another 
        parallel data instance. This is done by first stripping punctuation and numerical characters and 
        setting the source and target sentences to lowercase. Second the sentence is added to a set of 
        stripped versions of the parallel sentences. If the parallel sentence unit is not already in the set, we add 
        it to the set and move on. If the parallel sentence unit is in the set already, it means we've 
        seen it before and it must be a duplicate. We add the index of that sentence to the list of indices to remove.
        Finally, we remove all the sentences at the collected indeces.
        Args:
            nodes (list): list of lists of source and target strings

        Returns:
            the list of nodes without any duplicate nodes
        """
        to_remove = []
        stripped_set = set()

        for i in range(len(nodes)):
            src_stripped = ''.join([i for i in nodes[i][0].lower() if i.isalpha()])
            tgt_stripped = ''.join([i for i in nodes[i][1].lower() if i.isalpha()])
            src_and_target_stripped = (src_stripped, tgt_stripped)

            # add to set, if it is in set already, add index to to_remove, otherwise add it to set.
            if src_and_target_stripped in stripped_set:
                to_remove.append(i)
            else:
                stripped_set.add(src_and_target_stripped)

        return self.delete_indices(nodes, to_remove, 'remove_fuzzy_duplicates')

    def remove_duplicates(self, nodes):
        """
        Removes all duplicate instances of source and target. Two parallel sentences are
        considered a duplicate when all characters from both the source
        and the target of one parallel data instance are exactly the same as another.
        """
        to_remove = []
        tuple_set = set()

        for i in range(len(nodes)):
            src_and_target = (nodes[i][0], nodes[i][1])

            # add to set, if it is in set already, add index to to_remove, otherwise add it to set.
            if src_and_target in tuple_set:
                to_remove.append(i)
            else:
                tuple_set.add(src_and_target)

        return self.delete_indices(nodes, to_remove, 'remove_duplicates')

    def remove_when_missing_alpha_chars(self, nodes):
        """
        Removes all nodes where either the source or target sentence has no alphabetic characters.

        Args:
            nodes (list): list of lists of source and target strings

        Returns:
            list: the same list with said nodes removed.
        """
        def has_alpha(s):
            for c in s:
                if c.isalpha():
                    return True
            return False

        n = len(nodes)
        bad = []
        for i in range(n):
            if not has_alpha(nodes[i][0]) or not has_alpha(nodes[i][1]):
                bad.append(i)
        return self.delete_indices(nodes, bad, 'remove_when_missing_alpha_chars')    

    def remove_regex_patterns(self, nodes):
        """
        Iterates through the list of regular expressions provided by the config parameter
        'remove_regex_patterns' and searches each node for that pattern; if a match occurs,
        the entire unit is deleted.

        Args:
            nodes (list): list of lists of source and target strings

        Returns:
            list: the updated nodes with bad units removed
        """
        nodes = self._remove_regex_patterns_helper(nodes, True)
        nodes = self._remove_regex_patterns_helper(nodes, False)
        return nodes
    
    def _remove_regex_patterns_helper(self, nodes, tgt):
        params = [self.src_params, self.tgt_params][tgt]

        if 'remove_regex_patterns' in params:
            for p in params['remove_regex_patterns']:
                bad_indices = []
                p = re.compile(p)
                for i, n in enumerate(nodes):
                    if p.search(n[tgt]):
                        bad_indices.append(i)
                if self.verbose:
                    print(f"\t\tRemoving {len(bad_indices)} units that matched the pattern: {p.pattern}")
                nodes = self.delete_indices(nodes, bad_indices, 'remove_regex_patterns')
                bad_indices.clear()
        return nodes

    def remove_footnotes(self, nodes):
        """
        Removes all footnotes from the source and target sentences. Footnotes are defined as a decimal value of size 1 or more 
        that occurs at the end of a segment without a space between the last word and the decimal value. For example,
        "This is a sentence with a footnote1" and "And He will also mend us if we turn to Him in faith and repent of the harm we have caused.36" 
        would be considered a footnote. Also, looks for regex \"\d+ such as "He said, "this is a quote"3 and he liked it."

        Args:
            nodes (list): list of lists of source and target strings
        
        Returns:
            list: the same list with the footnotes removed
        """
        src_count = 0
        tgt_count = 0

        footnote_pattern = re.compile(r'(?<=[^\s–\-—\/\-,:#$%]\b)(?<!\d\.)(\d+)$')
        other_pattern = re.compile(r'(?<=[a-z]{2})\d+$|\"\d+')

        for i in range(len(nodes)):
            src_match = footnote_pattern.search(nodes[i][0])
            tgt_match = footnote_pattern.search(nodes[i][1])
            if src_match:
                src_count += 1
                nodes[i][0] = nodes[i][0][:src_match.start()]
            if tgt_match:
                tgt_count += 1
                nodes[i][1] = nodes[i][1][:tgt_match.start()]

        for i in range(len(nodes)):
            src_match = other_pattern.search(nodes[i][0])
            tgt_match = other_pattern.search(nodes[i][1])
            if src_match:
                src_count += 1
                nodes[i][0] = nodes[i][0][:src_match.start()]
            if tgt_match:
                tgt_count += 1
                nodes[i][1] = nodes[i][1][:tgt_match.start()]

        

        if self.verbose:
            print(f'\t\tRemoved {src_count} source footnotes and {tgt_count} target footnotes.')

        return nodes
        


    def normalize_regex_patterns(self, nodes):
        """
        Normalizes a regex pattern to the desired replacement string.

        Args:
            nodes (list): list of lists of source and target strings
        
        Returns:
            list: the same list with the regex patterns replaced with the desired replacement string
        """
        src_count = 0
        tgt_count = 0

        src_patterns = [(p, replacement) for p, replacement in self.src_params['normalize_regex_patterns'].items()]
        tgt_patterns = [(p, replacement) for p, replacement in self.tgt_params['normalize_regex_patterns'].items()]

        # if self.verbose:
        #     print(f'\nNormalizing regex patterns in source and target...')
        #     for pattern in src_patterns:
        #         print(f'    src {pattern[0]} --> {pattern[1]}')
        #     for pattern in tgt_patterns:
        #         print(f'    tgt {pattern[0]} --> {pattern[1]}')
    
        # for i, node in enumerate(nodes):
        #     for item in src_patterns:
        #         if re.search(item[0], node[0]):
        #             src_count += 1
        #         node[0] = re.sub(item[0], item[1], node[0])
        #     for item in tgt_patterns:
        #         if re.search(item[0], node[1]):
        #             tgt_count += 1
        #         node[1] = re.sub(item[0], item[1], node[1])

        # Loop through src patterns and tgt patterns
        for p in src_patterns:
            if self.verbose:
                pattern_loop = tqdm(total=len(nodes), desc=f'    src {p[0]} --> {p[1]}')
            for i, node in enumerate(nodes):
                    node[0], num_changes = re.subn(p[0], p[1], node[0])
                    src_count += num_changes

                    if self.verbose:
                        pattern_loop.update(1)

            if self.verbose:
                pattern_loop.close()
        
        for p in tgt_patterns:
            if self.verbose:
                pattern_loop = tqdm(total=len(nodes), desc=f'    tgt {p[0]} --> {p[1]}')
            for i, node in enumerate(nodes):
                    node[1], num_changes = re.subn(p[0], p[1], node[1])
                    tgt_count += num_changes

                    if self.verbose:
                        pattern_loop.update(1)

            if self.verbose:
                pattern_loop.close()

        if self.verbose:
            print()
            print(f'    {src_count} source nodes were modified')
            print(f'    {tgt_count} target nodes were modified')
        
        return nodes

    def remove_long_words(self, nodes):
        """
        Removes segments that contain words that are over 30 characters long
        Args:
            nodes (list): list of lists of source and target strings
        
        Returns:
            list: the same list with said nodes removed.
        """        
        remove = []

        if not self.src_params['remove_long_words'] or not self.tgt_params['remove_long_words']:
            if self.verbose:
                print('    Removing long words is disabled')
            return nodes

        src_initial_delim, src_final_delim = self.src_params['word_initial_delimiter'], self.src_params['word_final_delimiter']
        tgt_initial_delim, tgt_final_delim = self.tgt_params['word_initial_delimiter'], self.tgt_params['word_final_delimiter']

        # number of characters
        src_num_chars = self.src_params['longest_word_length']
        tgt_num_chars = self.tgt_params['longest_word_length']

        src_pattern = rf'{src_initial_delim}\S{{{src_num_chars},}}{src_final_delim}'
        tgt_pattern = rf'{tgt_initial_delim}\S{{{tgt_num_chars},}}{tgt_final_delim}'

        for i, node in enumerate(nodes):
            if self.src_params['remove_long_words'] and re.search(src_pattern, node[0]) or self.tgt_params['remove_long_words'] and re.search(tgt_pattern, node[1]):
                remove.append(i)

        return self.delete_indices(nodes, remove, 'remove_long_words')

    def normalize_character_set(self, nodes):
        nodes = self._normalize_character_set_helper(nodes, True)
        nodes = self._normalize_character_set_helper(nodes, False)
        return nodes

    def _normalize_character_set_helper(self, nodes, targ):
        params = [self.src_params, self.tgt_params][targ]

        if 'normalize_characters' in params:
            self._replace_characters(nodes, params['normalize_characters'], targ)

        sents = list(zip(*nodes))[targ]

        if 'allowed_characters' in params:
            allowed = params['allowed_characters']
            if self.verbose:
                print(f'Using strict character set for {["source", "target"][targ]} side')
                # all_list = sorted((c, ord(c), unicodedata.name(c, 'no name')) for c in allowed)
                # print('Allowed characters:\n{}'.format(all_list))
            bad = self._strict_character_set(sents, allowed, targ)
        else:
            if self.verbose:
                print(f'Using statistical character set for {["source", "target"][targ]} side')
            bad = self._statistical_character_set(
                sents,
                params['character_frequency_cutoff'],
                params['block_frequency_cutoff'],
                targ
            )

        return self.delete_indices(nodes, bad, 'normalize_character_set')

    def _replace_characters(self, nodes, replace, targ):
        if self.verbose:
            print(f'\nReplacing keys in character set with values for {["SOURCE", "TARGET"][targ]} language:')
            print(replace)
        for i, n in enumerate(nodes):
            s = n[targ]
            out = []
            rep = False
            for c in s:
                if c in replace:
                    out.append(replace[c])
                    rep = True
                else:
                    out.append(c)
            if rep:
                nodes[i][targ] = ''.join(out)

    def _strict_character_set(self, sents, allowed, targ):
        bad = []
        counts = Counter()
        inval_chars = set()
        for i, s in enumerate(sents):
            counts.update(s)
            for c in s:
                if c not in allowed:
                    inval_chars.add(c)
                    bad.append(i)
                    break

        if self.verbose:
            val_list = sorted((c, ord(c)) for c in allowed)
            inval_list = sorted((c, ord(c)) for c in inval_chars)

            # Write to terminal
            print('\tValid characters:\n{}'.format(val_list))
            print('\tInvalid characters:\n{}'.format(inval_list))

            # Write to files
            self._record_char_sets(char_list=val_list, counts=counts, val=True, statistical=False, targ=targ)
            self._record_char_sets(char_list=inval_list, counts=counts, val=False, statistical=False, targ=targ)
            
        return bad

    def _statistical_character_set(self, sents, character_frequency_cutoff, block_frequency_cutoff, targ):
        counts = Counter()
        for s in sents:
            counts.update(set(s))

        total = len(sents)

        bfreq = [0]*len(blocks_left) 
        bmap = {} # maps character to block index
        for k, v in counts.items():
            v /= total
            counts[k] = v
            ind = bisect(blocks_left, ord(k))-1
            if ind >= 0 and ord(k) < blocks_right[ind]:
                bmap[k] = ind
                bfreq[ind] += v

        for i in range(len(blocks_left)):
            bfreq[i] /= (blocks_right[i] - blocks_left[i] + 1)**0.5
        
        invalid = set()
        for k, f in counts.items():
            bf = bfreq[bmap[k]] if k in bmap else 0
            if f < character_frequency_cutoff and bf < block_frequency_cutoff:
                # print(f"k: {k}, f: {f}, bf: {bf}")
                invalid.add(k)

        if self.verbose:
            val_list = sorted((c, ord(c)) for c in counts.keys() if c not in invalid)
            inv_list = sorted((c, ord(c)) for c in invalid)

            # Print info to terminal
            print('\tCharacter frequency cutoff: {}'.format(character_frequency_cutoff))
            print('\tBlock frequency cutoff: {}'.format(block_frequency_cutoff))
            print('\tTotal characters: {}'.format(len(counts)))
            print('\tValid characters:\n{}'.format(val_list))
            print('\tInvalid characters:\n{}'.format(inv_list))

            # Write info to files
            self._record_char_sets(val_list, counts, val=True, statistical=True, targ=targ, total=total)
            self._record_char_sets(inv_list, counts, val=False, statistical=True, targ=targ, total=total)

        bad = []
        for i, s in enumerate(sents):
            for c in s:
                if c in invalid:
                    bad.append(i)
                    break

        return bad

    def _record_char_sets(self, char_list, counts, val, statistical, targ, total=None):
        filename = f"{self.char_dir}{['src', 'tgt'][targ]}_{['invalid', 'valid'][val]}_chars.txt"
        with open(filename, mode='w', encoding='utf8') as f:
            f.write(f"{['INVALID', 'VALID'][val]} CHARACTERS FOR {['SRC', 'TGT'][targ]} LANGUAGE - {['STRICT', 'STATISTICAL'][statistical]}\n")
            f.write(f"{'char':<6}{'dec':<8}{'name':<45}{'count':<9}\n")
            for (c, dec) in char_list:
                if statistical:
                    f.write(f"{c:<6}{dec:<8}{unicodedata.name(c, 'no name'):<45}{int(counts[c] * total):<8}\n")
                else:
                    f.write(f"{c:<6}{dec:<8}{unicodedata.name(c, 'no name'):<45}{counts[c]:<8}\n")
        return

    def remove_too_long(self, nodes):
        nodes = self._remove_too_long_helper(nodes, False)
        nodes = self._remove_too_long_helper(nodes, True)
        return nodes

    def _remove_too_long_helper(self, nodes, targ):
        squares_length = 0
        sum_length = 0
        for n in nodes:
            l = len(n[targ])
            sum_length += l
            squares_length += l*l

        n = len(nodes)
        mean = sum_length/n
        var = squares_length/n - mean**2
        sd = var**0.5
        TOL_SD = [self.src_params, self.tgt_params][targ]['maximum_length_sd']
        tol = mean + TOL_SD*sd

        bad = []
        for i, n in enumerate(nodes):
            if len(n[targ]) > tol:
                bad.append(i)
        if self.verbose:
            print(('\nSource', 'Target')[targ] + '\n\tmean length:\t{:.2f}\n\tcutoff length:\t{:.2f}'.format(mean, tol), end='')
        return self.delete_indices(nodes, bad, 'remove_too_long')

    def check_sentence_length_ratios(self, nodes):
        """
        Checks the ratio of the length of the source sentence to the length of the target sentence, 
        and removes all nodes where either ratio exceeds a certain cutoff point. Since this function
        assumes that no source or target node has a length of 0, the remove_empty_segments() function
        should probably be run immediately before this one.

        Args:
            nodes (list): list of lists of source and target strings

        Returns:
            list: the same list with said nodes removed.
        """
        num_std = self.tgt_params['sent_length_ratio_cutoff']

        squares1, sum1, squares2, sum2 = 0, 0, 0, 0
        for i in range(len(nodes)):
            n = nodes[i]
            sub1 = len(n[0]) / len(n[1])
            sum1 += sub1
            squares1 += sub1*sub1

            sub2 = len(n[1]) / len(n[0])
            sum2 += sub2
            squares2 += sub2*sub2

        n = len(nodes)
        mean1 = sum1/n
        var1 = squares1/n - mean1**2
        sd1 = var1**0.5
        tol1 = self.tgt_params['length_ratio_sd']*sd1

        mean2 = sum2/n
        var2 = squares2/n - mean2**2
        sd2 = var2**0.5
        tol2 = self.tgt_params['length_ratio_sd']*sd2

        bad = []
        for i in range(n):
            if abs(len(nodes[i][0])/len(nodes[i][1]) - mean1) > tol1 or abs(len(nodes[i][1])/len(nodes[i][0]) - mean2) > tol2:
                bad.append(i)

        return self.delete_indices(nodes, bad, 'check_sentence_length_ratios')

    def remove_unbalanced_brackets(self, nodes):
        """
        Removes brackets from the source and target sentences that are not balanced.
        Args:
            nodes (list): a list of 2-element lists, the first corresponding to source text and the second to corresponding target text
        Returns:
            The list of nodes with items containing unbalanced brackets removed
        """
        def mismatched(txt):
            bracket_pairs = {
                '(': ')', 
                '{': '}', 
                '[': ']'
            }
            stack = []
            starts = bracket_pairs.keys()
            ends = bracket_pairs.values()
            mismatched = False
            for c in txt:
                if c in starts:
                    stack.append(c)
                elif c in ends:
                    if len(stack) == 0 or not bracket_pairs[stack[-1]] == c:
                        return True
                    else:
                        stack = stack[:-1]
            if len(stack) > 0:
                return True
            return False

        for i, n in enumerate(nodes):
            if mismatched(n[0]):
                # remove the brackets
                n[0] = re.sub(r'[\(\)\{\}\[\]]', '', n[0])
            if mismatched(n[1]):
                # remove the brackets
                n[1] = re.sub(r'[\(\)\{\}\[\]]', '', n[1])
        
        return nodes

    def remove_segments_with_curly_brackets(self, nodes):
        """
        Removes all nodes that contain curly brackets in either the source or target text.
        Args:
            nodes (list): a list of 2-element lists, the first corresponding to source text and the second to corresponding target text
        Returns:
            The list of nodes with items containing curly brackets removed
        """

        to_remove = []
        for i, n in enumerate(nodes):
            if '{' in n[0] or '}' in n[0] or '{' in n[1] or '}' in n[1]:
                to_remove.append(i)
        
        return self.delete_indices(nodes, to_remove, 'remove_segments_with_curly_brackets')

    def remove_too_short(self, nodes):
        """
        Removes segments with source or target sentences that are too short. A raw string (set as self.word_delimiter, with default values r'\b') matching word delimiters or word boundaries is used to 
        determine the number of words in a sentence. The number of words in a sentence is then compared to a threshold value (set as self.min_num_words) to determine if the sentence is too short.
        This implementation uses the regex [^\W\d_]+ to match any sequence of word characters, excluding digits and non-underscore characters.

        Args:
            nodes (list): a list of 2-element lists, the first corresponding to source text and the second to corresponding target text
        Returns:
            The list of nodes with items containing too short sentences removed
        """

        if self.tgt_params['CJK']:
            # Only do it for the source nodes
            src_initial_delim, src_final_delim = self.src_params['word_initial_delimiter'], self.src_params['word_final_delimiter']
            src_p = re.compile(rf'{src_initial_delim}[^\W\d_]+{src_final_delim}')
            too_short = []
            for i, n in enumerate(nodes):
                if len(src_p.findall(n[0])) < self.src_params['min_num_words']:
                    too_short.append(i)

            # for CJK lanugages, we want to count the number of characters in the target sentence
            for i, n in enumerate(nodes):
                if len(n[1]) < self.tgt_params['min_num_words']:
                    too_short.append(i)
            
            return self.delete_indices(nodes, too_short, 'remove_too_short')

        src_initial_delim, src_final_delim = self.src_params['word_initial_delimiter'], self.src_params['word_final_delimiter']
        tgt_initial_delim, tgt_final_delim = self.tgt_params['word_initial_delimiter'], self.tgt_params['word_final_delimiter']
        src_p = re.compile(rf'{src_initial_delim}[^\W\d_]+{src_final_delim}')
        tgt_p = re.compile(rf'{tgt_initial_delim}[^\W\d_]+{tgt_final_delim}')
        too_short = []
        for i, n in enumerate(nodes):
            if len(src_p.findall(n[0])) < self.src_params['min_num_words'] or len(tgt_p.findall(n[1])) < self.tgt_params['min_num_words']:
                too_short.append(i)
        return self.delete_indices(nodes, too_short, 'remove_too_short')

    def remove_do_not_translate(self, nodes):
        """
        Removes segments with source or target sentences that contain the string 'DO_NOT_TRANSLATE'.

        Args:
            nodes (list): a list of 2-element lists, the first corresponding to source text and the second to corresponding target text
        Returns:
            The list of nodes with items containing the do not translate string removed
        """
        p = re.compile(r'DO NOT TRANSLATE', re.IGNORECASE)
        dnt = []
        for i, n in enumerate(nodes):
            if p.search(n[0]) or p.search(n[1]):
                dnt.append(i)
        return self.delete_indices(nodes, dnt, 'remove_do_not_translate')

    def condense_repeated_chars(self, nodes):
        """
        Condenses sequences of 5 or more repeated periods, hyphens, underscores, or space-period pairs into 
        sequences of 3 instances of the character. While perhaps not strictly necessary, this is done to
        simplify and shorten the strings and to re-balance the ratio of alphabetic characters to non-alphabetic.

        Args:
            nodes (list): a list of 2-element lists, the first corresponding to source text and the second to corresponding target text

        Returns:
            The list of nodes with repeated characters condensed.
        """
        for n in nodes:
            for i in (0,1):
                n[i] = re.sub(r'(\.{5,})', r'...', n[i]) # Condense 5 or more periods to 3
                n[i] = re.sub(r'(-{5,})', r'---', n[i]) # Condense 5 or more hyphens to 3
                n[i] = re.sub(r'(_{5,})', r'___', n[i]) # Condense 5 or more underscores to 3
                n[i] = re.sub(r'([ \.]{5,})', r'...', n[i]) # Condense 5 or more spaces-periods to 3 periods
        return nodes

    def remove_nonalpha(self, nodes):
        """
        Removes segments with source or target sentences that contain too high of a ratio of non-alphabetic characters.

        Args:
            nodes (list): a list of 2-element lists, the first corresponding to source text and the second to corresponding target text
        Returns:
            The list of nodes with items containing too high of a ratio of non-alphabetic characters removed
        """
        # I could definitely optimize this code for efficiency a lot more
        num_std_src = self.src_params['nonalpha_cutoff']
        num_std_tgt = self.tgt_params['nonalpha_cutoff']
        ratios_src, ratios_tgt = [], []
        to_delete = []
        for n in nodes:
            count_nonalpha_src = 0
            count_nonalpha_tgt = 0
            for c in n[0]:
                count_nonalpha_src += int(not c.isalpha())
            for c in n[1]:
                count_nonalpha_tgt += int(not c.isalpha())
            ratios_src.append(count_nonalpha_src / len(n[0]))
            ratios_tgt.append(count_nonalpha_tgt / len(n[1]))
                
        assert(len(ratios_src) == len(nodes))
        assert(len(ratios_tgt) == len(nodes))

        mean_src = sum(ratios_src)/len(ratios_src)
        mean_tgt = sum(ratios_tgt)/len(ratios_tgt)
        std_src = statistics.stdev(ratios_src)
        std_tgt = statistics.stdev(ratios_tgt)

        cutoff_src = mean_src + num_std_src*std_src
        cutoff_tgt = mean_tgt + num_std_tgt*std_tgt

        for i, n in enumerate(nodes):
                if ratios_src[i] > cutoff_src or ratios_tgt[i] > cutoff_tgt:
                    to_delete.append(i)
        return self.delete_indices(nodes, to_delete, 'remove_nonalpha')


    def edit_distance(self, nodes):
        bad_indices = []
        run_step = self.tgt_params['use_edit_distance'] #FIXME - only looks at tgt config right now
        if run_step and self.verbose:
            print(f"\nRemoving pairs with too close an edit distance")
        elif self.verbose:
            print(f"\nEdit distance step disabled")
            return nodes
        
        if run_step:
            raw_cutoff = self.tgt_params['min_valid_edit_dist_raw']
            ratio_cutoff = self.tgt_params['min_valid_edit_dist_ratio']
            for i, n in enumerate(nodes):
                if editdistance.eval(n[0], n[1]) < min(raw_cutoff, ratio_cutoff * min(len(n[0]), len(n[1]))):
                    bad_indices.append(i)
                    if len(bad_indices) % 500 == 0 and self.verbose: # Comment these out or change the % eventually
                        print('\n' + n[0],'\n' + n[1])
        return self.delete_indices(nodes, bad_indices, 'edit_distance')


    def remove_only_url(self, nodes):
        """
        Removes segments with source or target sentences that are just a url.

        Args:
            nodes (list): a list of 2-element lists, the first corresponding to source text and the second to corresponding target text
        Returns:
            The list of nodes with items that are just a url removed
        """
        to_delete = []
        for i, n in enumerate(nodes):
            if " " not in n[0] and "." in n[0]: # Only check the source in case of languages without spaces.
                to_delete.append(i)

        # if self.verbose:
        #     with open('only_url.txt', 'w') as f:
        #         for i in to_delete:
        #             f.write(nodes[i][0] + '\t' + nodes[i][1] + '\n')
        return self.delete_indices(nodes, to_delete, 'remove_only_url')