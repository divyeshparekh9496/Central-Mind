"""Train pointwise relevance learning; choose regularization on grouped train queries.

The BEIR test qrels are used once, after selection; they are SciFact's labeled
retrieval evaluation split, not its private claim-verification leaderboard.
"""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import random
import re
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import GroupShuffleSplit
import sklearn
from services.rag.retrieval import BM25Index, FEATURES


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def qrels(path):
    result = {}
    with Path(path).open() as handle:
        for row in csv.DictReader(handle,delimiter='\t'):
            if int(row['score']) > 0:
                result.setdefault(row['query-id'],set()).add(row['corpus-id'])
    return result


def metrics(ids, relevant):
    flags = [int(doc in relevant) for doc in ids]
    rr = next((1/(i+1) for i,value in enumerate(flags[:10]) if value),0)
    dcg = sum(value/math.log2(i+2) for i,value in enumerate(flags[:10]))
    ideal = sum(1/math.log2(i+2) for i in range(min(10,len(relevant))))
    return {'mrr_at_10':rr,'ndcg_at_10':dcg/ideal if ideal else 0,
            'recall_at_5':sum(flags[:5])/max(1,len(relevant)),
            'candidate_recall_at_50':sum(flags[:50])/max(1,len(relevant))}


def normalize(text):
    return re.sub(r'\W+',' ',text.lower()).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data',default='data/scifact')
    parser.add_argument('--output',default='models/evidence_ranker.json')
    args = parser.parse_args()
    root=Path(args.data)
    corpus=read_jsonl(root/'corpus.jsonl')
    docs=[{'id':str(d['_id']),'title':d.get('title',''),'text':d['text']} for d in corpus]
    queries={str(q['_id']):q['text'] for q in read_jsonl(root/'queries.jsonl')}
    train, test=qrels(root/'qrels/train.tsv'),qrels(root/'qrels/test.tsv')
    # Prevent paraphrase-identical query texts appearing in both labeled splits.
    heldout_text={normalize(queries[q]) for q in test}
    removed=[q for q in train if normalize(queries[q]) in heldout_text]
    train={q:docs for q,docs in train.items() if q not in removed}
    index=BM25Index(docs)
    byid={doc['id']:i for i,doc in enumerate(docs)}
    rng=random.Random(42)
    trainids=sorted(train)
    groups=[normalize(queries[q]) for q in trainids]
    split=GroupShuffleSplit(n_splits=1,test_size=.2,random_state=42)
    a,b=next(split.split(trainids,groups=groups))
    fitids=[trainids[i] for i in a];validids=[trainids[i] for i in b]
    def samples(ids):
        x,y=[],[]
        for q in ids:
            found=index.search(queries[q],len(docs))
            scores=dict(found)
            positives={byid[d] for d in train[q]}
            negatives=[i for i,_ in found if i not in positives][:15]
            negatives+=rng.sample([i for i in range(len(docs)) if i not in positives],5)
            for i in sorted(positives | set(negatives)):
                x.append(index.features(queries[q],i,scores.get(i,0)))
                y.append(int(i in positives))
        return x,y
    x,y=samples(fitids)
    def evaluate(model, ids, labels):
        output=[]
        for q in ids:
            found=index.search(queries[q],50)
            features=[index.features(queries[q],i,score) for i,score in found]
            scores=model.decision_function(features) if features else []
            learned=[i for (i,_),_ in sorted(zip(found,scores),key=lambda pair:-pair[1])]
            for name,ranked in [('bm25',[i for i,_ in found]),('learned',[i for i in learned])]:
                output.append({'query_id':q,'controller':name,**metrics([docs[i]['id'] for i in ranked],labels[q])})
        return output
    validation=[]
    for c in (.1,1,10):
        model=make_pipeline(StandardScaler(),LogisticRegression(C=c,class_weight='balanced',max_iter=1000,random_state=42))
        model.fit(x,y)
        rows=evaluate(model,validids,train)
        score=float(np.mean([r['ndcg_at_10'] for r in rows if r['controller']=='learned']))
        validation.append((score,c))
    score,c=max(validation,key=lambda value:(value[0],-value[1]))
    x,y=samples(trainids)
    model=make_pipeline(StandardScaler(),LogisticRegression(C=c,class_weight='balanced',max_iter=1000,random_state=42))
    model.fit(x,y)
    scaler,clf=model.steps[0][1],model.steps[1][1]
    artifact={'version':1,'algorithm':'pointwise_logistic_learning_to_rank',
              'features':FEATURES,'mean':scaler.mean_.tolist(),'scale':scaler.scale_.tolist(),
              'weights':clf.coef_[0].tolist(),'intercept':float(clf.intercept_[0]),
              'seed':42,'regularization_C':c,'train_queries':len(trainids),'train_pairs':len(y),
              'corpus_documents':len(docs),'dataset':'BEIR SciFact',
              'trained_at':datetime.now(timezone.utc).isoformat(),
              'scikit_learn_version':sklearn.__version__}
    path=Path(args.output);path.parent.mkdir(exist_ok=True,parents=True)
    path.write_text(json.dumps(artifact,indent=2)+'\n')
    rows=evaluate(model,sorted(test),test)
    summary={}
    for name in ('bm25','learned'):
        subset=[r for r in rows if r['controller']==name]
        summary[name]={key:float(np.mean([r[key] for r in subset])) for key in ('mrr_at_10','ndcg_at_10','recall_at_5','candidate_recall_at_50')}
    report={'dataset':'BEIR SciFact','evaluation_queries':len(test),'training_queries':len(train),
            'removed_exact_query_overlap':removed,'validation_groups':len(validids),
            'validation_C_scores':[{'C':c,'ndcg_at_10':score} for score,c in validation],
            'chosen_C':c,'seed':42,'summary':summary,
            'model_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'limitations':['One split/seed; no claim verification or answer-quality measurement.',
                           'Same BM25 top-50 candidates for both methods; no injected gold evidence in evaluation.',
                           'Relevance is annotated evidence retrieval, including supporting AND refuting documents.',
                           'Unjudged documents treated as nonrelevant; domain transfer to general web pages is unmeasured.']}
    provenance=Path('data/scifact-provenance.json')
    if provenance.exists():report['data_provenance']=json.loads(provenance.read_text())
    Path('docs').mkdir(exist_ok=True)
    Path('docs/retrieval-evaluation.json').write_text(json.dumps(report,indent=2)+'\n')
    with Path('docs/retrieval-evaluation.csv').open('w') as handle:
        writer=csv.DictWriter(handle,fieldnames=list(rows[0]),lineterminator="\n");writer.writeheader();writer.writerows(rows)
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    main()
