from sklearn.feature_extraction.text import CountVectorizer
import logging
from scipy.stats import chisquare
import met
import pandas as pd
import numpy as np

from .TwoSampleHC import two_sample_pvals, HC, binom_test_two_sided

def exact_multinomial_test(x, p) : # slow
    assert(len(x) == len(p))
    n_max = 40
    p = np.array(p) / np.sum(p)
    n = sum(x)
    if n > n_max or sum(x) == 0 :
        return chisquare(x, p * n)[1]
    all_multi_cases = [tup[0] for tup in met.onesided_exact_likelihood(x, [1,1,1])]
    probs = scipy.stats.multinomial.pmf(x=all_multi_cases, n=n, p=p)
    pval = probs[probs <= probs[all_multi_cases.index(list(x))]].sum()
    return pval

class CompareDocs :
    def __init__(self, **kwargs) :
        self.pval_type = kwargs.get('pval_type', 'multinom')
        self.vocab = kwargs.get('vocabulary', [])
        self.max_features = kwargs.get('max_features', 3000)
        self.min_cnt = kwargs.get('min_count', 3)
        self.ng_range = kwargs.get('ngram_range', (1,1))

        self.counts_df = pd.DataFrame()
        self.num_of_docs = np.nan
        self.names = []
        
    def test_doc(self, doc, stbl=True, gamma=.2) : 
    """
    Test a new document against existing documents by combining binomial allocation
    P-values from each document. 
    """
    
        logging.debug(f"Testing a new doc...")            
        if type(doc) == pd.DataFrame :
            # Count words in a dataframe
            logging.debug(f"Doc is a dataframe.")
            dfi = pd.DataFrame(data.term.value_counts()).rename(columns={'term' : 'n'})
        else :
            logging.debug(f"Assuming doc is a string.")
            dfi = self.count_words(doc)
            dfi = dfi.set_index('term')

        logging.debug(f"Doc contains {dfi.n.sum()} terms.")
        df = self.HCT(gamma=gamma, stbl=stbl)
        dfi['T(test)'] = dfi.n.sum()
        dfi = dfi.rename(columns = {'n' : 'n(test)'})
        df = df.join(dfi, how='left')
        
        
        for name in self.names:
            cnt1 = df['n(test)']
            cnt2 = df['n' + name]
            pv, p = two_sample_pvals(cnt1, cnt2, ret_p=True)
            
            df[f'pval({name})'] = pv
            df[f'sign({name})'] = np.sign(cnt1 - (cnt1 + cnt2) * p)
            df[f'score({name})'] = -2*np.log(df[f'pval({name})']) * df['thresh']
    
        return df

        
    def count_words(self, text) :
        df = pd.DataFrame()

        pat = r"\b\w\w+\b|[a\.!?%\(\);,:\-\"\`]"
        pat = r"\b\w\w+\b"
        # term counts
        if len(self.vocab) == 0:
            tf_vectorizer = CountVectorizer(token_pattern=pat, 
                                            max_features=self.max_features,
                                            ngram_range=self.ng_range
                                           )
        else:
            tf_vectorizer = CountVectorizer(token_pattern=pat,
                                            vocabulary=self.vocab,
                                            ngram_range=self.ng_range
                                           )
            
        tf = tf_vectorizer.fit_transform([text])
        vocab = tf_vectorizer.get_feature_names()
        tc = np.array(tf.sum(0))[0]

        df = pd.concat([df, pd.DataFrame({'term': vocab, 'n': tc})])
        return df
    
    def fit(self, lo_texts) :
        df = pd.DataFrame()
        if self.vocab == [] : # build vocabulry from data
            logging.debug("Building vocabulary from data")
            df_tot = self.count_words(" ".join(lo_texts))
            self.vocab = list(df_tot[df_tot.n >= self.min_cnt]['term'])
        
        df['term'] = self.vocab
        df['n'] = 0
        df = df.set_index('term')
            
        for i,txt in enumerate(lo_texts) :
            name = f"{i+1}"
            self.names += [name]
            logging.debug(f"Processing {name}...")
            dfi = self.count_words(txt).set_index('term')
            logging.debug(f"Found {dfi.n.sum()} terms.")
            df['n'] += dfi.n 
            dfi['T' + name] = dfi.n.sum()
            dfi = dfi.rename(columns = {'n' : 'n' + name})
            df = df.join(dfi, how='left', rsuffix=name)
        
        self.num_of_docs = i + 1
        
        self.counts_df = df
        
    def get_pvals(self) :
        if self.num_of_docs < 2 :
            logging.error("Not enough columns.")
            return np.nan
        df = self.counts_df.copy()
        if self.num_of_docs > 2 :
            logging.info("Using multinomial tests. May be slow.")
            acc_x = []
            acc_p = []
            
            acc_x = [df[c] for c in df if c == 'n']

            df['x'] = df.filter(regex='n[0-9]').to_records(index=False).tolist()
            df['p'] = df.filter(regex='T[0-9]').to_records(index=False).tolist()
            pv = df.apply(lambda r : exact_multinomial_test(r['x'], r['p']), axis = 1)
        
        else :
            logging.info("Using binomial tests.")
            pv = two_sample_pvals(df.n1, df.n2)
            
        df['pval'] = pv
        return df


    def HCT(self, gamma=.2, stbl=True) :
        """
        Return a DataFrame after applying HC threshold
        
        """
        
        df = self.get_pvals()

        hc, thr = HC(df['pval'], stbl=stbl).HCstar(gamma=gamma)
        df['HC'] = hc
        df['thresh'] = df['pval'] < thr
        return df
        