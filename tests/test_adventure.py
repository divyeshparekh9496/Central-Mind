import json
from pathlib import Path
import tempfile
import unittest
from services.adventure import AdventureService, MISSIONS, update_mastery


class AdventureTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'adventure.db'
        self.service=AdventureService(self.path)
        self.session='explorer_test_123'

    def test_bayes_update_matches_formula(self):
        self.assertAlmostEqual(update_mastery(.25,True),(.225/(.225+.25))*.88+.12)
        self.assertLess(update_mastery(.25,False),.25)
        for correct in (True,False):
            p=.25
            for _ in range(30):
                p=update_mastery(p,correct)
                self.assertTrue(0 <= p <= 1)
        with self.assertRaises(ValueError):update_mastery(float('nan'),True)

    def answer_question(self,topic,correct=True):
        item=self.service.start(self.session,topic)
        q=next(q for q in MISSIONS[topic]['questions'] if q['id']==item['question']['id'])
        choice=q['answer'] if correct else (q['answer']+1)%3
        return item,self.service.answer(self.session,item['attempt_id'],choice)

    def test_correct_answer_changes_topic_and_next_question_level(self):
        first,result=self.answer_question('planets')
        self.assertTrue(result['correct']);self.assertTrue(result['star_earned'])
        self.assertGreater(result['learner']['topics']['planets']['mastery'],.45)
        self.assertEqual(result['learner']['topics']['saturn']['mastery'],.25)
        next_item=self.service.start(self.session,'planets')
        q=next(q for q in MISSIONS['planets']['questions'] if q['id']==next_item['question']['id'])
        self.assertEqual(q['difficulty'],2)

    def test_wrong_answer_encourages_without_removing_stars(self):
        self.answer_question('planets')
        _,result=self.answer_question('saturn',False)
        self.assertFalse(result['star_earned'])
        self.assertIn('Good exploring',result['feedback'])
        self.assertEqual(result['learner']['stars'],1)

    def test_replayed_submission_is_idempotent(self):
        item,result=self.answer_question('stars')
        replay=self.service.answer(self.session,item['attempt_id'],0)
        self.assertEqual(replay,result)
        self.assertEqual(self.service.state(self.session)['stars'],1)

    def test_repeated_question_does_not_farm_stars_or_mastery(self):
        for _ in range(3):self.answer_question('saturn')
        before=self.service.state(self.session)
        _,result=self.answer_question('saturn')
        self.assertFalse(result['mastery_updated'])
        self.assertFalse(result['star_earned'])
        self.assertEqual(result['learner']['stars'],before['stars'])
        self.assertEqual(result['learner']['topics'],before['topics'])

    def test_session_isolation_and_delete(self):
        item,_=self.answer_question('blackholes')
        with self.assertRaises(ValueError):self.service.answer('other_explorer_123',item['attempt_id'],1)
        self.assertEqual(self.service.state('other_explorer_123')['stars'],0)
        self.service.forget(self.session)
        self.assertEqual(self.service.state(self.session)['discoveries'],0)
        with self.assertRaises(ValueError):self.service.answer(self.session,item['attempt_id'],1)

    def test_graded_state_survives_restart(self):
        self.answer_question('planets')
        self.assertEqual(AdventureService(self.path).state(self.session)['stars'],1)

    def test_no_answer_keys_in_public_missions_or_questions(self):
        self.assertTrue(all('questions' not in m for m in self.service.missions()))
        q=self.service.start(self.session,'stars')['question']
        self.assertNotIn('answer',q);self.assertNotIn('explanation',q)
        self.assertEqual(len(q['choices']),3)

    def test_invalid_input_cannot_record_learning(self):
        with self.assertRaises(ValueError):self.service.start('bad','stars')
        with self.assertRaises(ValueError):self.service.start(self.session,'unknown')
        item=self.service.start(self.session,'stars')
        for choice in (True,3,-1,'0'):
            with self.assertRaises(ValueError):self.service.answer(self.session,item['attempt_id'],choice)
        self.assertEqual(self.service.state(self.session)['stars'],0)

    def test_offline_guide_is_labeled_and_has_source_review_date(self):
        result=self.service.guide('Tell me about black holes')
        self.assertEqual(result['mode'],'offline_guide')
        self.assertEqual(result['topic'],'blackholes')
        self.assertTrue(result['sources'][0]['url'].startswith('https://science.nasa.gov/'))
        self.assertEqual(result['sources'][0]['reviewed_on'],'2026-10-17')
        self.assertEqual(self.service.guide('what is my name')['sources'],[])

    def test_successful_retry_can_earn_star_without_recounting_mastery(self):
        first,_=self.answer_question('planets',False)
        self.answer_question('planets',False)
        self.answer_question('planets',False)
        item,result=self.answer_question('planets',True)
        self.assertEqual(item['question']['id'],first['question']['id'])
        self.assertTrue(result['star_earned'])
        self.assertFalse(result['mastery_updated'])
