import pandas as pd
import numpy as np
from tqdm import *
from utils import to_docTermCounts, n_most_frequent_words
from FreqTable import FreqTable


class MultiTable(object) :
    """
    model for classification of frequency tables based on
    frequency similarity

    Args:
        data -- is a list of frequency tables
        vocab -- is a global vocabulary 
        stbl -- a parameter determinining type of HC statistic.
        randomize -- randomized P-values or not
    """
    def __init__(self, data, vocab=[], stbl=True, randomize=False) :
        self._randomize=randomize
        self._stbl=stbl
        self._classifyer=None

        self.sync_tables()

        return None

    def train_classifyer(method=None) :
        "train classifyer"
        return None

    def sync_tables(self): 
        "Synchronize vocabulary of all talbes"
        return None

    def predict(self, x, method='min_HC') :
        "attribute table x to one of the classes"
        return None

    def intraclass_stats(self):
        """Compute similarity of each pair of classes within the model."""
        return None

    def interclass_stats(self, wrt_cls = []):
        """Compute similarity of each sample with respect to a class.
        (use sample_stats on each sample in the dataset)

        """
        return None

    def sample_stats(self, smp_id, cls_id, wrt_cls = [], LOO = False) :
        """ stats wrt to all classes in list wrt_cls of 
            a single sample within the model. 
         """
        return None
            


class AuthorshipAttributionMulti(object):
    """
    model for text classification using word frequency data and HC-based 
    testing. 

    Args:
        data -- is a DataFrame with columns doc_id|author|text
                  (author represents the class idnetifyer or 
                    training label).
        vocab -- reduce word counts for this set (unless vocab == []).
        vocab_size -- extract vocabulary of this size 
                      (only if vocab == []).
        ngram_range -- ngram parameter for term tf_vectorizer
        stbl -- a parameter determinining type of HC statistic.
        words_to_ignore -- tell tokenizer to ignore words in
                           this list.
    """
    def __init__(self,
                 data,
                 vocab=[],
                 vocab_size=100,
                 words_to_ignore=[],
                 ngram_range=(1, 1),
                 stbl=True,
                 flat=False,
                 randomize=False,
                 ):
        """
        Args:
            data -- is a DataFrame with columns doc_id|author|text
                      (author represents the class idnetifyer or 
                        training label)
            vocab -- reduce word counts for this set (unless vocab == [])
            vocab_size -- extract vocabulary of this size 
                          (only if vocab == [])
            ngram_range -- ngram parameter for term tf_vectorizer
            stbl -- a parameter determinining type of HC statistic
            words_to_ignore -- tell tokenizer to ignore words in
                               this list
        """

        self._AuthorModel = {}  #:  list of FreqTable objects, one for
        #: each author.
        self._vocab = vocab  #: joint vocabulary for the model.
        self._ngram_range = ngram_range  #: the n-gram range of text
        #: in the model.
        self._stbl = stbl  #:  type of HC statistic to use.
        self._flat = flat
        self._randomize = randomize #: randomize pvalue or not

        if len(self._vocab) == 0:  #common vocabulary
            vocab = n_most_frequent_words(list(data.text),
                                          n=vocab_size,
                                          words_to_ignore=words_to_ignore,
                                          ngram_range=self._ngram_range)
        self._vocab = vocab

        #compute author-models
        lo_authors = pd.unique(data.author)
        for auth in lo_authors:
            data_auth = data[data.author == auth]
            print("\t Creating author-model for {} using {} features..."\
                .format(auth, len(self._vocab)))

            self._AuthorModel[auth] = self.to_docTermTable(
                                list(data_auth.text),
                                document_names=list(data_auth.doc_id)
                                )
            print("\t\tfound {} documents and {} relevant tokens."\
            .format(len(data_auth),
                self._AuthorModel[auth]._counts.sum()))

        #self.compute_author_models()

    def to_docTermTable(self, X, document_names=[]):
        """Convert raw input X into a FreqTable object. 

        Override this fucntion to process other input format. 

        Args:     
            X -- list of texts 
            document_names -- list of strings representing the names
                              of each text in X

        Returs:
            FreqTable object
        """

        dtm, _ = to_docTermCounts(X,
                            vocab=self._vocab,
                            ngram_range=self._ngram_range)

        if self._flat == True:
            dtm = dtm.sum(0)
            document_names = ["Sum of {} docs".format(len(document_names))]

        return FreqTable(dtm,
                    feature_names=self._vocab,
                    sample_ids=document_names,
                    stbl=self._stbl,
                    randomize=self._randomize
                    )

    def compute_author_models(self):
        """ compute author models after a change in vocab """

        for auth in self._AuthorModel:
            am = self._AuthorModel[auth]
            am.change_vocabulary(self._vocab)
            print("Changing vocabulary for {}. Found {} relevant tokens."\
                .format(auth, am._counts.sum()))

    def predict(self,
            x,
            method='HC',
            unk_thresh=1e6,
            LOO=False
            ):
        """
        Attribute text x with one of the authors or '<UNK>'. 

        Args:
            x -- string representing the test document 
            method -- designate which score to use. Supported method:
            'HC', 'HC_rank', 'chisq', 'chisq_pval', 'cosine'
            unk_thresh -- minimal score below which the text is 
            attributed to one of the authors in the model and not assigned
            the label '<UNK>'.
            LOO -- indicates whether to compute rank in a leave-of-out mode
            It leads to more accurate rank-based testing but require more 
            computations. 

        Returns:
            pred -- one of the keys in self._AuthorModel or '<UNK>'
            marg -- ratio of second smallest score to smallest scroe

        Note:
            Currently scores 'HC', 'rank' and 'cosine'
            are supported. 
        """

        if len(self._AuthorModel) == 0:
            raise IndexError("no pre-trained author models found")
            return None

        cand = '<UNK>'
        min_score = unk_thresh
        margin = unk_thresh

        Xdtb = self.to_docTermTable([x])

        for i, auth in enumerate(self._AuthorModel):
            am = self._AuthorModel[auth]
            
            if method == 'HC' or method == 'HC_rank':
                HC, rank, feat = am.get_HC_rank_features(Xdtb, LOO=LOO)
                score = HC
                if method == 'HC' :
                    score = HC
                else :
                    score = rank
            elif method == 'cosine':
                cosine = am.get_CosineSim(Xdtb)
                score = cosine
            elif method == 'chisq' or method == 'chisq_pval' :
                chisq, chisq_pval = am.get_ChiSquare(Xdtb)
                if method == 'chisq' :
                    score = chisq
                else :
                    score = 1 - chisq_pval

            if score < min_score: # find new minimum
                margin = min_score / score
                min_score = score
                cand = auth
            elif score / min_score < margin : # make sure to track the margin
                margin = score / min_score
        return cand, margin

    def internal_stats_corpus(self):
        """Compute scores of each pair of corpora within the model.
            
        Returns: 
            a dataframe with rows: 
            doc_id|author|HC|ChiSq|cosine|rank|wrt_author

            doc_id -- the document identifyer.
            wrt_author -- author of the corpus against which the
                          document is tested.
            HC, ChiSq, cosine -- HC score, Chi-Square score, and 
                    cosine similarity, respectively, between the 
                    document and the corpus.
            rank -- the rank of the HC score compared to other
                    documents within the corpus.
        """

        
        df = pd.DataFrame()

        for auth0 in tqdm(self._AuthorModel): # go over all authors
            md0 = self._AuthorModel[auth0]
            for auth1 in self._AuthorModel:  # go over all corpora
                if auth0 < auth1:       # test each pair only once
                    md1 = self._AuthorModel[auth1]
                    HC, rank, feat = md0.get_HC_rank_features(md1)
                    chisq, chisq_pval = md0.get_ChiSquare(md1)
                    cosine = md0.get_CosineSim(md1)
                    df = df.append(
                        {
                            'author': auth1,
                            'wrt_author': auth0,
                            'HC': HC,
                            'HC_rank' : rank,
                            'chisq': chisq,
                            'chisq_pval' : chisq_pval,
                            'cosine': cosine,
                            'no_docs (author)': len(md1.get_sample_ids()),
                            'no_docs (wrt_author)': len(md0.get_sample_ids()),
                            'no_tokens (author)': md1._counts.sum(),
                            'feat': list(feat)
                        },
                        ignore_index=True)
        return df

    def get_doc_stats(self,
     doc_id,
     author,
     wrt_authors = [],
     LOO = False) :
        """ stats wrt to all authors in list wrt_authors of 
            a single document within the model. 
         """

        try :
            md0 = self._AuthorModel[author]
            lo_docs = md0.get_sample_ids()
            i = lo_docs[doc_id]
            dtbl = md0.get_sample_as_table(doc_id)
        except ValueError:
            print("Document {} by author {}".format(doc_id,author)\
                +"is either missing or contains no model features")
            return None


        df = pd.DataFrame()

        if len(wrt_authors) == 0:
            # evaluate with resepct to all authors in the model
            wrt_authors = self._AuthorModel

        for auth1 in wrt_authors:
            md1 = self._AuthorModel[auth1]
                
            if author == auth1:
                HC, rank, feat = md1.get_HC_rank_features(
                    dtbl, LOO=LOO, within=True
                    )
                chisq, chisq_pval = md1.get_ChiSquare(dtbl,
                                                 within=True)
                chisq23, chisq23_pval = md1.get_ChiSquare(
                    dtbl,
                    within=True,
                    lambda_="cressie-read")
                cosine = md0.get_CosineSim(dtbl, within=True)
            else:
                HC, rank, feat = md1.get_HC_rank_features(dtbl, LOO=LOO)
                chisq, chisq_pval = md1.get_ChiSquare(dtbl)

                chisq23, chisq23_pval = md1.get_ChiSquare(dtbl,
                    lambda_="cressie-read")
                cosine = md0.get_CosineSim(dtbl)
            df = df.append(
                {
                    'doc_id': doc_id,
                    'author': author,
                    'wrt_author': auth1,
                    'HC': HC,
                    'chisq': chisq,
                    'chisq_pval' : chisq_pval,
                    'chisq23' : chisq23,
                    'cosine': cosine,
                    'HC_rank': rank,
                    'feat': list(feat)
                },
                ignore_index=True)
        return df


    def internal_stats(self, authors = [], 
            wrt_authors=[], LOO=False, verbose=False):
        """
        Compute scores of each document with respect to the corpus of
        each author. When tested against its own corpus, the document
        is removed from that corpus. 
        
        Args:
        authors -- subset of the authors in the model. Test only documents
                belonging to these authors
        wrt_authors -- subset of the authors in the model with respect
                to which the scores of each document are evaluated.
                If empty, evaluate with respect to all authors.
        LOO -- indicates whether to compute rank in a leave-of-out mode.
            This mode provides more accurate rank-based testing but require more 
            computations.

        Returns: 
            Pandas dataframe with rows: 
            doc_id|author|HC|ChiSq|cosine|rank|wrt_author
            where:
            doc_id -- the document identifyer. 
            wrt_author -- author of the corpus against which the
                          document is tested.
            HC, ChiSq, cosine -- HC score, Chi-Square score, and cosine
                    similarity, respectively, between the document and
                    the corpus.
            rank -- the rank of the HC score compared to other documents 
            within the corpus.
        """

        df = pd.DataFrame()

        if len(authors) == 0:
            # evaluate with resepct to all authors in the model
            authors = self._AuthorModel

        for auth0 in authors :
            #tqdm(wrt_authors):
            md0 = self._AuthorModel[auth0]
            #for auth1 in self._AuthorModel:
            #    md1 = self._AuthorModel[auth1]
            lo_docs = md0.get_sample_ids()
            for dn in lo_docs:
                if verbose :
                    print("testing {} by {}".format(dn,auth0))
                df = df.append(self.get_doc_stats(dn, auth0,
                 wrt_authors = wrt_authors,
                  LOO = LOO), ignore_index=True)

        return df

    def predict_stats(self, x, wrt_authors=[], LOO=False):
        """ Returns a pandas dataframe with columns representing the 
        statistics: HC score, ChiSquare, rank (of HC), cosine similarity
        where each one is obtained by comparing the input text 'x' to each
        corpus in the model.
        
        Args:
            x -- input text (list of strings)
            wrt_authors -- subset of the authors in the model with respect
                to which the scores of each document are evaluated.
                If empty, evaluate with respect to all authors.
            LOO -- indicates whether to compute rank in a leave-of-out
                    mode. It leads to more accurate rank-based testing 
                    but require more computations.

        Returns:
            dataframe with rows: 
            doc_id|author|HC|ChiSq|cosine|rank|wrt_author

            doc_id -- the document identifyer.
            wrt_author -- author of the corpus against which the
                         document is tested.
            HC, ChiSq, cosine -- HC score, Chi-Square score, and cosine
                                 similarity, respectively, between the 
                                 document and the corpus.
            rank -- the rank of the HC score compared to other documents 
                    within the corpus.
        """
        # provides statiscs on decision wrt to test sample text
        xdtb = self.to_docTermTable([x])

        if len(wrt_authors) == 0:
            # evaluate with resepct to all authors in the model
            wrt_authors = self._AuthorModel

        df = pd.DataFrame()
        for auth in tqdm(wrt_authors):
            md = self._AuthorModel[auth]
            HC, rank, feat = md.get_HC_rank_features(xdtb, LOO=LOO)
            chisq, chisq_pval = md.get_ChiSquare(xdtb)
            cosine = md.get_CosineSim(xdtb)
            df = df.append(
                {
                    'wrt_author': auth,
                    'HC': HC,
                    'chisq': chisq,
                    'chisq_pval' : -chisq_pval,
                    'HC_rank': rank,
                    'feat': feat,
                    'cosine': cosine,
                },
                ignore_index=True)
        return df

    def stats_list(self, data, wrt_authors=[], LOO=False):
        """
        Same as internal_stats but for a list of documents 

        Arguments:
            data -- list of documents with columns: doc_id|author|text

        Returns:
            dataframe with rows: 
            doc_id|author|HC|ChiSq|cosine|rank|wrt_author

            doc_id -- the document identifyer.
            wrt_author -- author of the corpus against which the
                         document is tested.
            HC, ChiSq, cosine -- HC score, Chi-Square score, and cosine
                                 similarity, respectively, between the 
                                 document and the corpus.
            rank -- the rank of the HC score compared to other documents 
                    within the corpus.
        """

        df = pd.DataFrame()

        if len(wrt_authors) == 0:
            # evaluate with resepct to all authors in the model
            wrt_authors = self._AuthorModel

        for auth0 in tqdm(wrt_authors):
            md0 = self._AuthorModel[auth0]
            for r in data.iterrows() :
                dtbl =  self.to_docTermTable([r[1].text])
                chisq, chisq_pval = md0.get_ChiSquare(dtbl)
                cosine = md0.get_CosineSim(dtbl)
                HC, rank, feat = md0.get_HC_rank_features(dtbl,
                                                        LOO=LOO)
                df = df.append(
                    {
                        'doc_id': r[1].doc_id,
                        'author': r[1].author,
                        'wrt_author': auth0,
                        'HC': HC,
                        'chisq': chisq,
                        'chisq_pval' : chisq_pval,
                        'cosine': cosine,
                        'HC_rank': rank,
                        'feat': list(feat)
                    },
                    ignore_index=True)
        return df

    def two_author_test(self, auth1, auth2, stbl=None,
                within=False, randomize=False) :
        return self._AuthorModel[auth1]\
                  .two_table_test(self._AuthorModel[auth2],
                   stbl=stbl,
                   within=within,
                   randomize=randomize
                   )
        

    def reduce_features(self, new_feature_set):
        """
            Update the model to a new set of features. 
        """
        self._vocab = new_feature_set
        self.compute_author_models()

    def test_against(self, x, wrt_authors = [], stbl=None) :
        """ 
        two sample test of x vs the corpora in the list 
        wrt_authors.
        
        Args:
            x -- input text (list of strings)
            wrt_authors -- subset of the authors in the model
                with respect to which to compute HC and features.
                If empty, evaluate with respect to all authors.

        Returns:
            data frame of counts, pvalues, and signed z scores
        """

        if stbl == None :
            stbl = self._stbl

        xdtb = self.to_docTermTable([x])

        if len(wrt_authors) == 0:
            # evaluate with resepct to all authors in the model
            wrt_authors = self._AuthorModel

        #aggregate models
        agg_model = None
        for auth in tqdm(wrt_authors):
            md = self._AuthorModel[auth]
            agg_model = md.add_table([agg_model])
            agg_model.collapse_dtm()
        
        return agg_model.two_table_test(xdtb, stbl=stbl)

    def train_classifyer(self, classifyer) :
        def dtm_to_featureset(dtm) :
            fs = []
            for sm_id in dtm.get_sample_ids() :
                dtl = dtm.get_sample_as_table(sm_id)
                fs += [dtl.get_featureset()]
            return fs

        train_set = []
        for auth in self._AuthorModel :
                md =  self._AuthorModel[auth]
                fs = dtm_to_featureset(md)
                train_set += [(f, auth) for f in fs]

        classifyer.train(train_set)


    
class AuthorshipAttributionMultiBinary(object):
    """ Use pair-wise tests to determine most likely author. 
        It does so by creating AuthorshipAttributionMulti object for each 
        pair of authors and reduces the features of this object. 

        The interface is similar to AuthorshipAttributionMultiBinary
    """
    def __init__(
            self,
            data,
            vocab=[],
            vocab_size=100,
            words_to_ignore=[],
            global_vocab=False,
            ngram_range=(1, 1),
            stbl=True,
            reduce_features=False,
            randomize=False,
    ):
        # train_data is a dataframe with at least fields: author|doc_id|text
        # vocab_size is an integer controlling the size of vocabulary

        self._AuthorPairModel = {}
        self._stbl = stbl
        self._randomize = randomize

        if len(vocab) == 0 :
            if global_vocab == True:
                if len(vocab) == 0:
                    #get top vocab_size terms
                    vocab = n_most_frequent_words(
                                    list(data.text),
                                    n=vocab_size,
                                    words_to_ignore=words_to_ignore,
                                    ngram_range=ngram_range)
            
        lo_authors = pd.unique(data.author)  #all authors
        lo_author_pairs = [(auth1, auth2) for auth1 in lo_authors\
                             for auth2 in lo_authors if auth1 < auth2 ]

        print("Found {} author-pairs".format(len(lo_author_pairs)))
        for ap in lo_author_pairs:  # AuthorPair model for each pair
            print("MultiBinaryAuthorModel: Creating model for {} vs {}..."\
                .format(ap[0],ap[1]))

            data_pair = data[data.author.isin(list(ap))]
            ap_model = AuthorshipAttributionMulti(
                                    data_pair,
                                    vocab=vocab,
                                    vocab_size=vocab_size,
                                    words_to_ignore=words_to_ignore,
                                    ngram_range=ngram_range,
                                    stbl=stbl,
                                    randomize=self._randomize
                                    )

            self._AuthorPairModel[ap] = ap_model
            if reduce_features == True:
                feat = self.reduce_features_for_author_pair(ap)
                print("Reduced to {} features...".format(len(feat)))
                
    def reduce_features_for_author_pair(self, auth_pair) :
        """
            Find list of features (tokens) discriminating two authors
            Reduce model to those features. 
            'auth_pair' is a key in self._AuthorPairModel
            returns the new list of features
        """
        ap_model = self._AuthorPairModel[auth_pair]

        md1 = ap_model._AuthorModel[auth_pair[0]]
        md2 = ap_model._AuthorModel[auth_pair[1]]
        
        _, _, feat = md1.get_HC_rank_features(md2)
        ap_model.reduce_features(list(feat))
        return ap_model._vocab

    def predict(self, x, method='HC', LOO=False):
        def predict_max(df1):
            # whoever has more votes or <UNK> in the 
            # case of a draw
            cnt = df1.pred.value_counts()
            imx = cnt.values == cnt.values.max()
            if sum(imx) == 1: 
                return cnt.index[imx][0] 
            else: #in the case of a draw
                return '<UNK>'

        df1 = self.predict_stats(x, LOO=LOO, method=method)

        predict = predict_max(df1)
        return predict

    def predict_stats(self, x, method='HC', LOO=False):
        # provides statiscs on decision wrt to test sample text
        df = pd.DataFrame()

        if len(self._AuthorPairModel) == 0:
            raise IndexError("no pre-trained author models found")

        for ap in self._AuthorPairModel:
            ap_model = self._AuthorPairModel[ap]

            pred, margin = ap_model.predict(x, method=method, LOO=LOO)
            df = df.append(
                {
                    'author1': ap[0],
                    'author2': ap[1],
                    'pred': pred,
                    'margin': margin,
                },
                ignore_index=True)
        return df
