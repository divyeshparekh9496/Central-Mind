import asyncio
from datetime import timedelta
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from services.rag.pipeline import PassageStore, RAGPipeline, chunk_text, utcnow
from services.rag.retrieval import BM25Index, EvidenceRanker
from services.research_agent import ResearchAgent
from ml.train_ranker import metrics


class RetrievalTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.db = str(Path(self.directory.name)/'passages.sqlite3')

    def document(self, text, url='https://example.test/solar', **extra):
        return dict(url=url,title='Solar research',text=text,**extra)

    def test_overlapping_chunks_are_bounded(self):
        chunks=list(chunk_text(' '.join(str(i) for i in range(400)),180,35))
        self.assertTrue(all(len(c.split()) <= 180 for c in chunks))
        self.assertEqual(chunks[0].split()[-35:], chunks[1].split()[:35])
        self.assertEqual(chunks[-1].split()[-1], '399')
        with self.assertRaises(ValueError):list(chunk_text('words',10,10))

    def test_update_replaces_all_old_chunks(self):
        store=PassageStore(self.db)
        first=store.upsert(self.document('outdated '*400))
        store.upsert(self.document('revised solar evidence'))
        docs=store.passages()
        self.assertEqual(len(docs),1)
        self.assertNotEqual(first['content_hash'],docs[0]['content_hash'])
        self.assertNotIn('outdated',docs[0]['text'])

    def test_expired_and_future_sources_are_excluded(self):
        store=PassageStore(self.db)
        store.upsert(self.document('old data',fetched_at=(utcnow()-timedelta(days=2)).isoformat()))
        self.assertEqual(store.passages(max_age_hours=24),[])
        store.upsert(self.document('future data',fetched_at=(utcnow()+timedelta(days=2)).isoformat()))
        self.assertEqual(store.passages(),[])
        with self.assertRaises(ValueError):store.upsert(self.document('data',fetched_at='2026-01-01T00:00:00'))

    def test_refresh_failure_does_not_reuse_previously_indexed_page(self):
        rag=RAGPipeline(self.db)
        rag.ingest([self.document('solar panels generate power')])
        self.assertTrue(rag.retrieve('solar panels'))
        self.assertEqual(rag.refresh_and_retrieve('solar panels',[]),[])

    def test_bm25_ranks_relevant_and_abstains_on_no_overlap(self):
        docs=[{'id':'a','title':'','text':'solar panel electricity'},
              {'id':'b','title':'','text':'ocean fish reef'}]
        ranker=EvidenceRanker()
        self.assertEqual(ranker.rank('solar panel',docs)[0]['id'],'a')
        self.assertEqual(ranker.rank('unmatchedword',docs),[])
        self.assertEqual(ranker.rank('solar',[]),[])

    def test_learned_artifact_and_provenance(self):
        path=Path('models/evidence_ranker.json')
        report=json.loads(Path('docs/retrieval-evaluation.json').read_text())
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),report['model_sha256'])
        ranker=EvidenceRanker(path)
        result=ranker.rank('solar cells',[{'title':'Solar cells','text':'Solar cells generate electricity','id':'a'}])
        self.assertEqual(result[0]['ranker'],'supervised_logistic_reranker')
        self.assertIsInstance(result[0]['relevance_score'],float)
        with self.assertRaises(FileNotFoundError):EvidenceRanker('/missing/ranker.json')

    def test_store_survives_restart_and_has_bound_citations(self):
        rag=RAGPipeline(self.db)
        rag.ingest([self.document('solar panels convert light into electricity')])
        hits=RAGPipeline(self.db).retrieve('solar panels')
        self.assertEqual(hits[0]['citation_id'],1)
        self.assertEqual(hits[0]['url'],'https://example.test/solar')
        self.assertIn('content_hash',hits[0])
        self.assertIn('fetched_at',hits[0])
        self.assertNotIn('published',hits[0])  # Fetch time does not invent publication.

    def test_metric_denominators_include_missing_relevant_documents(self):
        result=metrics(['x','b','a'],{'a','b','missing'})
        self.assertAlmostEqual(result['mrr_at_10'],.5)
        self.assertAlmostEqual(result['recall_at_5'],2/3)
        self.assertLess(result['ndcg_at_10'],1)


class FakeSearch:
    def __init__(self):
        self.searches=0
        self.text='Solar panels convert sunlight into electricity. '*8
        self.failed=False

    async def search(self, query, max_results=5):
        self.searches+=1
        return [{'title':'Failed source','url':'https://example.test/broken'},
                {'title':'Solar evidence','url':'https://example.test/good'}]

    async def fetch_content(self,url):
        if url.endswith('broken') or self.failed:
            raise RuntimeError('Simulated unavailable page')
        return self.text


class FakeModel:
    def __init__(self):self.prompts=[]
    def generate_content(self,prompt):
        self.prompts.append(prompt)
        return type('Response',(),{'text':'Solar panels convert sunlight into electricity [Source 1].'})()


class ResearchIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory=tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.search=FakeSearch()
        self.model=FakeModel()
        self.rag=RAGPipeline(str(Path(self.directory.name)/'index.db'))
        self.agent=ResearchAgent(generation_model=self.model,web_search=self.search,rag=self.rag)

    async def test_failed_extraction_cannot_shift_citation_to_wrong_source(self):
        result=await self.agent.research('solar panels','quick')
        self.assertTrue(result['citations'])
        self.assertTrue(all(c['url']=='https://example.test/good' for c in result['citations']))
        self.assertNotIn('https://example.test/broken',self.model.prompts[0])
        self.assertEqual(result['metadata']['ranker'],'bm25_only')

    async def test_same_question_is_refetched_and_changed_content_replaces_old(self):
        await self.agent.research('solar panels','quick')
        self.search.text='Solar panels now have revised evidence about electricity. '*8
        second=await self.agent.research('solar panels','quick')
        self.assertEqual(self.search.searches,2)
        self.assertFalse(second['metadata']['cache_hit'])
        self.assertTrue(all('revised' in d['text'] for d in self.rag.store.passages()))

    async def test_outage_abstains_instead_of_using_old_index_or_llm(self):
        await self.agent.research('solar panels','quick')
        calls=len(self.model.prompts)
        self.search.failed=True
        result=await self.agent.research('solar panels','quick')
        self.assertEqual(result['citations'],[])
        self.assertEqual(len(self.model.prompts),calls)
        self.assertEqual(result['metadata']['retrieval_status'],'no_current_evidence')

    async def test_snippet_fallback_is_identified(self):
        source={'title':'Solar','url':'https://example.test/broken','snippet':'Solar evidence snippet'}
        docs=await self.agent._extract_documents([source])
        self.assertEqual(docs[0]['evidence_kind'],'search_snippet')
        self.assertEqual(docs[0]['url'],source['url'])
