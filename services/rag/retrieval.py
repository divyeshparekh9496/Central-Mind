"""BM25 passage retrieval with supervised relevance reranking.

Scores rank relevance, not truth, entailment or calibrated confidence.
"""
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import re

STOP = set('a an the and or is are was were to of for in on at by with from as it this that be has have not'.split())
FEATURES = ['bm25', 'idf_cosine', 'query_coverage', 'title_coverage', 'jaccard',
            'bigram_coverage', 'log_length', 'numeric_coverage']


def tokens(text):
    return [t for t in re.findall(r'[a-z0-9]+', str(text).lower()) if t not in STOP]


class BM25Index:
    def __init__(self, documents):
        self.documents = list(documents)
        self.counts, self.postings = [], defaultdict(list)
        for i, doc in enumerate(self.documents):
            counts = Counter(tokens(doc.get('title', '')+' '+doc['text']))
            self.counts.append(counts)
            for token, count in counts.items():
                self.postings[token].append((i, count))
        self.lengths = [sum(c.values()) for c in self.counts]
        self.average = sum(self.lengths)/max(1, len(self.lengths))
        self.idf = {t: math.log(1+(len(self.documents)-len(p)+.5)/(len(p)+.5))
                    for t, p in self.postings.items()}

    def search(self, query, limit=50):
        scores = defaultdict(float)
        for token in set(tokens(query)):
            for i, tf in self.postings.get(token, []):
                scores[i] += self.idf[token]*tf*2.5/(tf+1.5*(.25+.75*self.lengths[i]/max(1,self.average)))
        return sorted(scores.items(), key=lambda pair: (-pair[1], str(self.documents[pair[0]].get('id',pair[0]))))[:limit]

    def features(self, query, index, bm25):
        q = tokens(query)
        qs, ds = set(q), set(self.counts[index])
        title = set(tokens(self.documents[index].get('title', '')))
        overlap = qs & ds
        weight = lambda t: self.idf.get(t, math.log(1+len(self.documents)))
        dot = sum(weight(t)**2 for t in overlap)
        norm = math.sqrt(sum(weight(t)**2 for t in qs)*sum(weight(t)**2 for t in ds))
        bigrams = set(zip(q, q[1:]))
        dt = tokens(self.documents[index]['text'])
        dbigrams = set(zip(dt, dt[1:]))
        numbers = {t for t in qs if t.isdigit()}
        return [float(bm25), dot/norm if norm else 0,
                len(overlap)/max(1,len(qs)), len(qs & title)/max(1,len(qs)),
                len(overlap)/max(1,len(qs | ds)), len(bigrams & dbigrams)/max(1,len(bigrams)),
                math.log1p(self.lengths[index]), len(numbers & ds)/max(1,len(numbers))]


class EvidenceRanker:
    def __init__(self, model_path=None, cross_encoder=None):
        self.model = None
        self.cross_encoder = None
        if cross_encoder:
            from sentence_transformers import CrossEncoder
            self.cross_encoder = CrossEncoder(cross_encoder, device='cpu')
            self.name = f'cross_encoder:{cross_encoder}'
        elif model_path:
            self.model = json.loads(Path(model_path).read_text())
            if self.model['features'] != FEATURES or self.model.get('version') != 1:
                raise ValueError('Unsupported evidence-ranker artifact.')
            self.name = 'supervised_logistic_reranker'
        else:
            self.name = 'bm25_only'

    def rank(self, query, documents, limit=6, candidates=50):
        index = BM25Index(documents)
        found = index.search(query, candidates)
        if self.cross_encoder and found:
            scores = self.cross_encoder.predict([(query, index.documents[i].get('title','')+' '+index.documents[i]['text']) for i,_ in found])
            ranked = [(i,float(score)) for (i,_),score in zip(found,scores)]
        elif self.model:
            ranked = []
            m = self.model
            for i, bm25 in found:
                features = index.features(query, i, bm25)
                score = m['intercept']+sum(w*(x-center)/scale for w,x,center,scale in
                                           zip(m['weights'],features,m['mean'],m['scale']))
                ranked.append((i,score))
        else:
            ranked = found
        ranked.sort(key=lambda pair: (-pair[1],str(index.documents[pair[0]].get('id',pair[0]))))
        return [dict(index.documents[i], relevance_score=score, ranker=self.name) for i,score in ranked[:limit]]
