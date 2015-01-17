'''
Created on 17.11.2014

@author: ruckt
'''

import re
from pprint import pprint

output_filename = 'gen2/navi-derivation.txt'
output_format = '"{term_norm}";{parents_norm}'
should_order = False

tiftang = '’'
long_bar = '–'
r_navi_word = tiftang + r"äa-zA-ZìÌ\-"+long_bar+"\+" # regex for one Na'vi word
r_navi_words = "["+r_navi_word+"\(\) ]+" # regex for a space separated, brace containg set of words
reg_braces = re.compile('\(.+?\)|«.+?»|[\(\)\-' + long_bar + tiftang + ']') # regex for enbraced stuff that can be omitted (e.g. tseng(e) -> tseng)
reg_term = re.compile('^(' + r_navi_words + ': )', re.MULTILINE) # regex for one navi term (always followed by a colon in the dict)
reg_translation = re.compile("(" + r_navi_words + r"?): (\[.*?\]) ([A-Z\,]*) (?:\(?([a-z\.]*)\)? )?(.+?)\n((\d+|[ÌA-Z][a-z]?)\n[^\|]+?)?\|\|"
                             .replace(' ', '(?: |\n)'), re.DOTALL) # regex for an entity in the dictionary, i.e. term, ipa, word source, word type, and translation
reg_derive = re.compile( r" \((derived|c\.w\.) from (.*?)\)" ) # regex for the derivation and compound word stuff
reg_allomorph = re.compile( "allomorph of ([".replace(' ', '(?: |\n)') + r_navi_word + ']+)' ) # regex for allomorph words
reg_sound = re.compile( r'\[sound\:[^\]]*\] ' ) # regex to clean out the [sound:*] tags in the anki list

parent_precedence_check = [('nga’','nga'),('yo’','yo')] # which derivation preceeds over another

def read_words_from(txt, inflections=None):
    # reads the information from the NaviDictionary.pdf (by Ctrl+A, Ctrl+C it into a file)
    # i.e. a list of words with translation, ipa, source and type
    
    new_txt = reg_term.sub(r'||\1', txt) # separate all translation entities by ||
    words = []
    inflection_occured = False
    for m in reg_translation.finditer(new_txt):
        #print(m.groups())
        term, ipa, word_src, word_type, transl = m.groups()[:5]
        word = {'term':term, 'ipa':ipa, 'word_src':word_src, 'word_type': word_type}
        transl = transl.replace('\n', ' ')
        derived_from_m = reg_derive.search(transl)
        allomorph_of_m = reg_allomorph.search(transl)
        transl = reg_allomorph.sub('', reg_derive.sub('', transl))
        word['translation'] = transl
        if derived_from_m:
            derive_type, derived_from = derived_from_m.groups()
            word['derive_type'] = derive_type
            word['derived_from'] = derived_from.split(' and ')
        if allomorph_of_m:
            word['allomorph_of'] = allomorph_of_m.group(1)
        if inflections is not None and ("%sa%s" % ((long_bar,)*2) == term or inflection_occured):
            inflections.add(word['term'])
            inflection_occured = long_bar + "yu" != term
        words.append(word)
    return words

def build_word_trees(words, inflections):
    # Find the correct parents and children for a word.
    # Really messed up
    word_trees = []
    dictionary_sub = {}
    dictionary_normal = {}
    words_dict = {}
    
    for w in words:
        words_dict[w['term']] = w
        if 'derived_from' in w:
            for df in w['derived_from']: # find parent words
                df_parts = reg_braces.sub('',df).split(' ')
                df_parts = df_parts[:(len(df_parts)+1)//2]
                for df_part in df_parts:
                    if df_part:
                        dictionary_sub.setdefault(df_part[0], []).append( ( df_part, w) )
                dictionary_normal.setdefault(df[0], []).append( ( df, w) )
        else:
            word_trees.append(w) # fill with root nodes
            
    for w in words: # assign the correct allomorph siblings
        if 'allomorph_of' in w:
            allo = w['allomorph_of']
            allo_w = words_dict.get(allo, None)
            if not allo_w and long_bar in w['term']:
                allo_w = words_dict.get(long_bar + allo)
                
            if allo_w:
                allo_w.setdefault('allomorph_siblings', []).append(w)
            else:
                print('*** ALLOMORPH NOT FOUND for ', w['term'])
                print(w)
                
    for w in words:
        children = []
        children_set = set()
        df_test = '%s %s' % (w['term'], w['translation']) # the "derivated from" parts always have the form "term translation", so we have to check, if this matches
        for dw in words: # find all the children of this word
            if (dw['term'] not in children_set and 
                    'derived_from' in dw):
                for df in dw['derived_from']:
                    if df_test.startswith(df):
                        children_set.add(dw['term'])
                        children.append(dw)
                        
        t = w['term'].replace(long_bar, '')
        t_notiftang = reg_braces.sub('', t)
        if t_notiftang[0] in dictionary_sub:
            for df, dw in dictionary_sub[t_notiftang[0]]:
                if dw['term'] not in children_set and len(t) > 1 and t_notiftang == reg_braces.sub('',df):
                    children_set.add(dw['term'])
                    children.append(dw)
        if t[0] in dictionary_normal:
            for df, dw in dictionary_normal[t[0]]:
                if dw['term'] not in children_set and df.startswith(t + ' '):
                    children_set.add(dw['term'])
                    children.append(dw)
            
        if w['term'] in inflections: # assign the inflections like tì- etc.
            regexes = []
            if w['term'][-1] == long_bar:
                regexes.append(re.compile('^%s[%s]+$' % (t_notiftang, r_navi_word)))
            if w['term'][0] == long_bar:
                regexes.append(re.compile('^[%s]+%s$' % (r_navi_word, t_notiftang)))
            if w['term'][-1] == '+':
                regexes.append(re.compile(('^%s[^'+tiftang+'t]+$') % t_notiftang))
            for wi in words:
                if not wi.get('parents', False):
                    continue
                for regex in regexes:
                    if wi['term'] != w['term'] and regex.match(wi['term']):
                        children.append(wi)
            
        if children: # assign all parents
            w['children'] = children
            for allo_w in w.get('allomorph_siblings', ()):
                allo_w['children'] = children
            for child in children:
                child.setdefault('parents', []).append( w['term'] ) 
                for allo_w in w.get('allomorph_siblings', ()):
                    child['parents'].append(allo_w['term'])
        
    for w in words:
        if 'parents' in w:
            for p in set( p1 for i,p1 in enumerate(w['parents']) 
                             for j,p2 in enumerate(w['parents']) if i!=j and p1==p2 ):
                w['parents'].remove(p)
            
            remove_parents_set = set()
            for pre1,pre2 in parent_precedence_check:
                if pre2 in w['parents']:
                    remove_parents_set.add(pre2 if pre1 in w['term'] else pre1)
            if remove_parents_set:
                print('remove parents:', remove_parents_set, w['parents'], w['term'])
            for parent in remove_parents_set:
                w['parents'].remove(parent)
                parent_w = words_dict[parent]
                for child in (c for c in parent_w.get('children',()) if c is w):
                    for i,c in enumerate(parent_w['children']):
                        if c is w:
                            del parent_w['children'][i]
                            break
    for w in words:
        if 'derived_from' in w and 'parents' in w and len(set(w['parents']) - inflections) != len(w['derived_from']):
            print('Unmatched parent:', w['term'], w['parents'], w['derived_from'])
            
        #if w['term'] in inflections:
        #    print('Inflection:', w['term'])
        #    for c in children:
        #        print('- ', c['term'], c['parents'])
        
        #word_trees.append(w)
    return word_trees
    
def recursive_flatten(wt, c2p:'child to parents', p2c:'parent to children', depth=0):
    if depth > 3:
        return
    for child in wt.get('children', ()):
        if child['term'] in c2p: 
            continue
        c2p[child['term']] = child['parents'] 
        for parent in child['parents']:
            p2c.setdefault(parent, []).append(child)
        #missmatch = len(''.join(c for c in child['term'] if not any(c in p for p in child['parents']) ))
        #match = sum( len(child['term']) - len(child['term'].replace(p,'')) for p in child['parents'] )
        # parent_match[child['term']] = missmatch - match
        recursive_flatten(child, c2p, p2c, depth + 1)

def ordered_words(word_trees):
    # Orders the words by significance and by parenthood
    # I.e. the root words are first in the list.
    #
    # Significance (stored as 'length', which has the inverse meaning):
    # L = |w| + 0.5(long_bar € w) - 0.5(tiftang € w) - 0.4|w_children|
    # a € b: a element of b
    
    for wt in word_trees: # this should be recursive, wtf tobi drunk
        wt['length'] = len(wt['term'])
        if '–' in wt['term']:
            wt['length'] += 0.5
        if tiftang in wt['term']:
            wt['length'] -= 0.5
        if 'children' in wt:
            wt['length'] -= 0.4*len(wt['children'])
        
    word_trees.sort(key = lambda wt: wt['length'])
    
    words = []
    children2parents = {}
    parent2children = {}
    for wt in word_trees:
        recursive_flatten(wt, children2parents, parent2children)
        
    occured_words = set()
    not_occured = set()
    for wt in word_trees:
        words.append(wt)
        occured_words.add(wt['term'])
        for child in parent2children.get(wt['term'], () ):
            if all( parent in occured_words for parent in children2parents.get( child['term'],() )):
                words.append(child)
                occured_words.add(child['term'])
                not_occured.discard(child['term'])
            else:
                not_occured.add(child['term'])
    return words
    
if __name__ == '__main__':
    import time
    start_time = time.time()
    inflections = set()
    print('Reading...')
    words = read_words_from(open('dict_pdf.txt', encoding='utf-8').read(), inflections)
    print('Foresting...')
    word_trees = build_word_trees(words, inflections)
    print('Ordering...')
    words = ordered_words(word_trees)
    print('Writing...')
    dict_anki = dict( reg_sound.sub('', line).split(';')[:2] for line in open('dict-navi-anki.txt', encoding='utf-8') )
    dict_ipa = dict( line.split('\t')[:2] for line in open('navidict.txt', encoding='utf-8') )
    dict_words = {}
    
    for w in words:
        dict_words[w['term']] = w
        w['de_translation'] = dict_anki.get(w['term'], ' ')[:-1]
        w['ipa_utf'] = dict_ipa.get(w['term'], None)
    
    dest_file = open(output_filename, 'w', encoding='utf-8')
    for w in words:
        deriv = '' if 'derive_type' not in w else '%s from %s' % (w['derive_type'], ' and '.join('%s (%s)' % (dw, dict_words[dw]['translation']) for dw in w['parents'] ) )
        parents = '" %s"' % '"," '.join(dw for dw in w.get('parents',[]))
        children = '"%s"' % '","'.join(child['term'] for child in w.get('children',[]))
        
        d = dict( term        = w['term'],
                  term_norm   = w['term'].replace(tiftang, "'").replace(long_bar, '-'),
                  ipa         = w['ipa_utf'] or '',
                  ipa_ascii   = w['ipa'] or '',
                  word_src    = w['word_src'] or '',
                  word_type   = w['word_type'] or '',
                  en_translation = w['translation'].replace(';', ','),
                  de_translation = w['de_translation'],
                  derivation  = deriv,
                  parents     = parents,
                  children    = children,
                  parents_norm = parents.replace(',', ';').replace(tiftang, "'").replace(long_bar, '-'),
                  children_norm = children.replace(',', ';').replace(tiftang, "'").replace(long_bar, '-')
                   )
        
        print(output_format.format(**d), file=dest_file)
    print('Finished in %.1fs' % (time.time() - start_time))
    