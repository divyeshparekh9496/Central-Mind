import os
from neo4j import GraphDatabase
from typing import List, Dict, Any

class KnowledgeGraphService:
    def __init__(self):
        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        user = os.getenv("NEO4J_USER", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "password")
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def add_concept(self, concept_name: str, description: str, category: str):
        """Add a fundamental astrophysics concept to the graph."""
        with self.driver.session() as session:
            session.execute_write(self._create_concept, concept_name, description, category)

    def add_relation(self, concept1: str, relation: str, concept2: str):
        """Link two concepts (e.g., 'Black Hole' -HAS_PROPERTY-> 'Event Horizon')."""
        with self.driver.session() as session:
            session.execute_write(self._create_relation, concept1, relation, concept2)

    def get_related_context(self, concept_name: str) -> List[Dict[str, Any]]:
        """Retrieve related concepts for 'infinite horizon' context."""
        with self.driver.session() as session:
            return session.execute_read(self._find_related, concept_name)

    @staticmethod
    def _create_concept(tx, name, desc, cat):
        query = (
            "MERGE (c:Concept {name: $name}) "
            "SET c.description = $desc, c.category = $cat "
            "RETURN c"
        )
        tx.run(query, name=name, desc=desc, cat=cat)

    @staticmethod
    def _create_relation(tx, c1, rel, c2):
        query = (
            "MATCH (a:Concept {name: $c1}), (b:Concept {name: $c2}) "
            "MERGE (a)-[r:RELATION {type: $rel}]->(b) "
            "RETURN r"
        )
        tx.run(query, c1=c1, c2=c2, rel=rel)

    @staticmethod
    def _find_related(tx, name):
        query = (
            "MATCH (c:Concept {name: $name})-[r]->(related) "
            "RETURN related.name as name, type(r) as relation, related.description as description"
        )
        result = tx.run(query, name=name)
        return [record.data() for record in result]
