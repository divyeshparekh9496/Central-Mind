"""Kid-friendly astronomy missions and auditable Bayesian knowledge tracing.

BKT parameters are configured priors, NOT fitted child-data model parameters.
No names, raw audio or free-form voice transcripts are persisted here.
"""
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import uuid

MISSION_DATA = [
    ('planets', 'Planet hop', 'Find our place in the solar system.', 'earth',
     'Our solar system has eight planets traveling around the Sun. Earth is our home, and Jupiter is the biggest planet.',
     'https://science.nasa.gov/solar-system/', [
        ('home',1,'Which planet is our home?',['Earth','Mars','Jupiter'],0,'Look beneath your feet!','Earth is our home planet.'),
        ('biggest',2,'Which is the biggest planet?',['Mercury','Jupiter','Venus'],1,'Think of a giant with a Great Red Spot.','Jupiter is the largest planet in our solar system.'),
        ('orbit',3,'What keeps planets moving around the Sun?',['Space wind','A giant string','Gravity'],2,'It is the same pull that keeps us on the ground.','Gravity pulls planets toward the Sun while their forward motion carries them around it.')]),
    ('saturn','Ring detective','Investigate Saturn and its icy rings.','saturn',
     'Saturn is a giant planet surrounded by rings made mostly of pieces of ice, with some rock and dust. Other giant planets have rings too!',
     'https://science.nasa.gov/saturn/facts/', [
        ('rings',1,'Which planet is famous for its bright rings?',['Earth','Saturn','Mars'],1,'Its name starts with S.','Saturn has a spectacular ring system.'),
        ('ice',2,'What are Saturn\'s rings mostly made of?',['Ice pieces','Fire','Clouds of air'],0,'Think of something cold that melts.','The rings are mostly pieces of ice, with some rock and dust.'),
        ('others',3,'Is Saturn the only planet with rings?',['Yes','No, Earth has rings','No, other giant planets do too'],2,'Jupiter, Uranus and Neptune have fainter rings.','All four giant planets in our solar system have rings.')]),
    ('blackholes','Black hole lookout','Investigate from a safe imaginary spaceship.','blackhole',
     'A black hole is a place where gravity is so strong that light cannot escape from inside its event horizon. It does not suck up everything in the universe. We can study glowing material around it.',
     'https://science.nasa.gov/universe/black-holes/', [
        ('escape',1,'Can light escape from inside a black hole\'s event horizon?',['Yes','Only at night','No'],2,'That boundary is called the point of no return.','Light cannot escape from inside the event horizon.'),
        ('boundary',2,'What is the black hole\'s point-of-no-return boundary called?',['Event horizon','Rainbow road','Moon gate'],0,'It is not a solid wall. Its name has two words.','The event horizon is the boundary beyond which light cannot escape.'),
        ('vacuum',3,'Does a black hole suck up everything, no matter how far away?',['Yes, everything','No, distance matters','Only planets'],1,'Its gravity depends on distance, just like other objects.','Black holes do not act like magical cosmic vacuum cleaners.')]),
    ('stars','Star explorer','Meet the star that lights our days.','sun',
     'The Sun is the star at the center of our solar system. It gives Earth light and warmth. Deep inside, nuclear fusion combines hydrogen into helium and releases energy.',
     'https://science.nasa.gov/sun/facts/', [
        ('sun',1,'What kind of object is our Sun?',['A planet','A star','A moon'],1,'It makes its own light.','The Sun is a star, and it is the closest star to Earth.'),
        ('energy',2,'What gives Earth most of its natural light and warmth?',['The Moon','Saturn','The Sun'],2,'It is the bright star we see in the daytime.','Sunlight brings energy to Earth.'),
        ('fusion',3,'What releases energy deep inside the Sun?',['Nuclear fusion','Burning wood','A giant battery'],0,'Hydrogen joins to form helium.','Nuclear fusion in the Sun\'s core releases energy.')]),
]
MISSIONS = {}
for topic,title,subtitle,art,intro,url,questions in MISSION_DATA:
    MISSIONS[topic] = {'id':topic,'title':title,'subtitle':subtitle,'art':art,'intro':intro,
                       'source_url':url,'reviewed_on':'2026-10-17',
                       'questions':[dict(id=f'{topic}:{qid}', difficulty=difficulty,prompt=prompt,
                                         choices=choices,answer=answer,hint=hint,explanation=explanation)
                                    for qid,difficulty,prompt,choices,answer,hint,explanation in questions]}


def update_mastery(prior, correct, learn=.12, guess=1/3, slip=.10):
    values=(prior,learn,guess,slip)
    if not all(math.isfinite(v) and 0 <= v <= 1 for v in values):
        raise ValueError('BKT probabilities must be finite and between zero and one.')
    known = prior*((1-slip) if correct else slip)
    unknown = (1-prior)*(guess if correct else (1-guess))
    posterior = known/(known+unknown) if known+unknown else prior
    return posterior+(1-posterior)*learn


def valid_session(value):
    if not re.fullmatch(r'[A-Za-z0-9_-]{8,80}',value):
        raise ValueError('Invalid explorer session.')
    return value


class AdventureService:
    def __init__(self, path=None):
        self.path=str(path or os.getenv('ADVENTURE_DB_PATH','data/adventure.sqlite3'))
        Path(self.path).parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS topic_mastery (session TEXT, topic TEXT, probability REAL, PRIMARY KEY(session,topic))')
            conn.execute('CREATE TABLE IF NOT EXISTS quiz_attempts (id TEXT PRIMARY KEY, session TEXT, topic TEXT, question TEXT, result TEXT, created_at TEXT)')

    def connect(self):
        return sqlite3.connect(self.path, timeout=20)

    def state(self, session):
        valid_session(session)
        with self.connect() as conn:
            mastery=dict(conn.execute('SELECT topic,probability FROM topic_mastery WHERE session=?',(session,)))
            results=conn.execute('SELECT topic,question,result FROM quiz_attempts WHERE session=? AND result IS NOT NULL',(session,)).fetchall()
        discoveries={(topic,question) for topic,question,result in results}
        stars=sum(json.loads(result).get('correct_for_reward',False) for _,_,result in results)
        return {'stars':stars,'discoveries':len(discoveries),
                'topics':{topic:{'mastery':mastery.get(topic,.25),
                                  'discoveries':sum(t==topic for t,_ in discoveries)} for topic in MISSIONS},
                'model':'Bayesian Knowledge Tracing','parameter_source':'configured; not fitted to learner data'}

    def missions(self):
        return [{k:v for k,v in m.items() if k!='questions'} for m in MISSIONS.values()]

    def start(self, session, topic):
        valid_session(session)
        if topic not in MISSIONS:raise ValueError('Unknown destination.')
        mastery=self.state(session)['topics'][topic]['mastery']
        desired=1 if mastery < .45 else 2 if mastery < .75 else 3
        with self.connect() as conn:
            counts=dict(conn.execute('SELECT question,COUNT(*) FROM quiz_attempts WHERE session=? AND topic=? AND result IS NOT NULL GROUP BY question',(session,topic)))
            # Prefer unseen questions, then the level nearest the mastery estimate.
            q=min(MISSIONS[topic]['questions'],key=lambda q:(counts.get(q['id'],0)>0,abs(q['difficulty']-desired),counts.get(q['id'],0),q['id']))
            attempt=uuid.uuid4().hex
            conn.execute('INSERT INTO quiz_attempts VALUES (?,?,?,?,NULL,?)',(attempt,session,topic,q['id'],datetime.now(timezone.utc).isoformat()))
        return {'attempt_id':attempt,'topic':topic,'question':{k:q[k] for k in ('id','prompt','choices','hint')},'learner':self.state(session)}

    def answer(self, session, attempt, choice):
        valid_session(session)
        if isinstance(choice,bool) or not isinstance(choice,int) or not 0 <= choice < 3:
            raise ValueError('Choose one of the three answers.')
        with self.connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            row=conn.execute('SELECT topic,question,result FROM quiz_attempts WHERE id=? AND session=?',(attempt,session)).fetchone()
            if not row:raise ValueError('Start a new discovery challenge first.')
            topic,qid,stored=row
            if stored:return dict(json.loads(stored),learner=self.state(session))
            q=next(q for q in MISSIONS[topic]['questions'] if q['id']==qid)
            correct=choice==q['answer']
            old=conn.execute('SELECT probability FROM topic_mastery WHERE session=? AND topic=?',(session,topic)).fetchone()
            prior=old[0] if old else .25
            # A repeated question is practice, not new evidence of mastery.
            previous=conn.execute('SELECT result FROM quiz_attempts WHERE session=? AND question=? AND result IS NOT NULL',(session,qid)).fetchall()
            seen=bool(previous)
            rewarded=any(json.loads(row[0]).get('correct_for_reward',False) for row in previous)
            probability=prior if seen else update_mastery(prior,correct)
            conn.execute('INSERT OR REPLACE INTO topic_mastery VALUES (?,?,?)',(session,topic,probability))
            result={'correct':correct,'feedback':('Cosmic discovery! ' if correct else 'Good exploring! Let\'s discover why. ')+q['explanation'],
                    'source_url':MISSIONS[topic]['source_url'],
                    'reviewed_on':MISSIONS[topic]['reviewed_on'],'mastery_updated':not bool(seen),
                    'star_earned':bool(correct and not rewarded),'topic':topic}
            # A later successful retry can earn its star, but never twice.
            result['correct_for_reward']=bool(correct and not rewarded)
            conn.execute('UPDATE quiz_attempts SET result=? WHERE id=?',(json.dumps(result),attempt))
        result['learner']=self.state(session)
        return result

    def forget(self, session):
        valid_session(session)
        with self.connect() as conn:
            conn.execute('DELETE FROM quiz_attempts WHERE session=?',(session,))
            conn.execute('DELETE FROM topic_mastery WHERE session=?',(session,))
        return {'forgotten':True}

    def guide(self, query, topic='planets'):
        query=query.lower()
        if any(word in query for word in ('black hole','event horizon')):topic='blackholes'
        elif any(word in query for word in ('saturn','ring')):topic='saturn'
        elif any(word in query for word in ('sun','star','fusion')):topic='stars'
        elif any(word in query for word in ('planet','earth','jupiter','solar system')):topic='planets'
        else:
            return {'response':'That is a wonderful space question! My offline explorer guide knows planets, Saturn, stars and black holes. Pick a destination to explore, or use the connected tutor for more questions.', 'topic':topic,'mode':'offline_guide','sources':[]}
        m=MISSIONS[topic]
        return {'response':m['intro']+' Want to try a discovery challenge?', 'topic':topic,
                'mode':'offline_guide','sources':[{'url':m['source_url'],'reviewed_on':m['reviewed_on']}]}
