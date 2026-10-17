"""Inspect persistent evidence retrieval locally, without a generation API key."""
import argparse
import json
from pathlib import Path
from services.rag.pipeline import RAGPipeline


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--db',default='data/rag.sqlite3')
    p.add_argument('--model',help='Optional trained JSON relevance model')
    p.add_argument('--cross-encoder',help='Optional pretrained Sentence Transformers model ID')
    sub=p.add_subparsers(dest='command',required=True)
    ingest=sub.add_parser('ingest')
    ingest.add_argument('file')
    ingest.add_argument('--title')
    ingest.add_argument('--url',help='Canonical source URL; defaults to the local file URI')
    search=sub.add_parser('search')
    search.add_argument('query')
    search.add_argument('--limit',type=int,default=6)
    args=p.parse_args()
    pipeline=RAGPipeline(args.db,args.model,args.cross_encoder)
    if args.command=='ingest':
        path=Path(args.file).resolve()
        doc={'url':args.url or path.as_uri(),'title':args.title or path.name,
             'text':path.read_text(),'evidence_kind':'user_supplied_local_file'}
        pipeline.ingest([doc])
        print(json.dumps({'ingested':doc['url'],'ranker':pipeline.ranker.name}))
    else:
        print(json.dumps({'query':args.query,'ranker':pipeline.ranker.name,
                          'passages':pipeline.retrieve(args.query,limit=args.limit)},indent=2))


if __name__=='__main__':
    main()
