"""Fact-checking service to verify information and reduce hallucinations."""
import re
from typing import List, Dict, Optional, Tuple
from collections import Counter


class FactChecker:
    """Service for verifying facts across multiple sources."""
    
    def __init__(self):
        self.verification_patterns = {
            "date": r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}[/-]\d{1,2}[/-]\d{1,2}',
            "number": r'\d+[.,]?\d*',
            "percentage": r'\d+\.?\d*%',
            "name": r'[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+',
        }
    
    def extract_claims(self, text: str, max_claims: int = 50) -> List[Dict[str, str]]:
        """
        Extract factual claims from text.
        
        Args:
            text: Text to extract claims from
            max_claims: Maximum number of claims to extract (prevents runaway processing)
            
        Returns:
            List of extracted claims with context
        """
        claims = []
        sentences = re.split(r'[.!?]+', text)
        
        for sentence in sentences[:200]:  # Limit sentences processed
            if len(claims) >= max_claims:
                break
            sentence = sentence.strip()
            if len(sentence) > 20:  # Filter out very short sentences
                # Identify potential factual claims
                if any(keyword in sentence.lower() for keyword in 
                       ['is', 'was', 'are', 'were', 'has', 'have', 'had', 
                        'according to', 'research shows', 'study found']):
                    claims.append({
                        "claim": sentence,
                        "type": self._classify_claim(sentence)
                    })
        
        return claims
    
    def _classify_claim(self, claim: str) -> str:
        """Classify the type of claim."""
        claim_lower = claim.lower()
        if any(word in claim_lower for word in ['date', 'year', 'when']):
            return "temporal"
        elif any(word in claim_lower for word in ['number', 'percent', 'amount', 'count']):
            return "numerical"
        elif any(word in claim_lower for word in ['person', 'who', 'name']):
            return "entity"
        else:
            return "general"
    
    def verify_claim(self, claim: str, sources: List[str]) -> Dict[str, any]:
        """
        Verify a claim against multiple sources.
        
        Args:
            claim: The claim to verify
            sources: List of source texts to check against
            
        Returns:
            Verification result with confidence score
        """
        claim_lower = claim.lower()
        supporting_sources = []
        contradicting_sources = []
        
        # Extract key terms from claim
        key_terms = self._extract_key_terms(claim)
        
        for i, source in enumerate(sources):
            source_lower = source.lower()
            match_score = self._calculate_match_score(claim_lower, source_lower, key_terms)
            
            if match_score > 0.5:
                supporting_sources.append({
                    "source_index": i,
                    "match_score": match_score
                })
            elif match_score < 0.3:
                # Check for contradictions
                if self._check_contradiction(claim_lower, source_lower):
                    contradicting_sources.append({
                        "source_index": i,
                        "match_score": match_score
                    })
        
        # Calculate confidence
        total_sources = len(sources)
        support_count = len(supporting_sources)
        contradiction_count = len(contradicting_sources)
        
        if total_sources == 0:
            confidence = 0.0
        else:
            confidence = (support_count - contradiction_count * 2) / total_sources
            confidence = max(0.0, min(1.0, confidence))
        
        return {
            "claim": claim,
            "confidence": confidence,
            "supporting_sources": len(supporting_sources),
            "contradicting_sources": len(contradicting_sources),
            "total_sources": total_sources,
            "verified": confidence >= 0.5
        }
    
    def _extract_key_terms(self, text: str) -> List[str]:
        """Extract key terms from text."""
        # Remove common stop words
        stop_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 
                     'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would'}
        
        words = re.findall(r'\b\w+\b', text.lower())
        key_terms = [w for w in words if w not in stop_words and len(w) > 3]
        
        # Return most frequent terms
        term_counts = Counter(key_terms)
        return [term for term, _ in term_counts.most_common(5)]
    
    def _calculate_match_score(self, claim: str, source: str, key_terms: List[str]) -> float:
        """Calculate how well a source matches a claim."""
        if not key_terms:
            return 0.0
        
        # Count matching key terms
        matches = sum(1 for term in key_terms if term in source)
        term_score = matches / len(key_terms) if key_terms else 0.0
        
        # Check for exact phrase matches
        phrase_score = 0.0
        claim_phrases = [p.strip() for p in re.split(r'[,\s]+', claim) if len(p.strip()) > 3]
        for phrase in claim_phrases[:3]:  # Check top 3 phrases
            if phrase in source:
                phrase_score += 0.2
        
        return min(1.0, term_score * 0.7 + phrase_score)
    
    def _check_contradiction(self, claim: str, source: str) -> bool:
        """Check if source contradicts the claim."""
        # Simple contradiction detection
        negation_words = ['not', 'no', 'never', 'none', 'neither', 'cannot', "can't"]
        claim_has_negation = any(word in claim for word in negation_words)
        source_has_negation = any(word in source for word in negation_words)
        
        # If one has negation and other doesn't, might be contradiction
        if claim_has_negation != source_has_negation:
            # Check if they're talking about the same thing
            claim_terms = set(self._extract_key_terms(claim))
            source_terms = set(self._extract_key_terms(source))
            overlap = len(claim_terms & source_terms) / len(claim_terms | source_terms) if (claim_terms | source_terms) else 0
            
            return overlap > 0.3
        
        return False
    
    def cross_reference(self, claims: List[str], sources: List[str], max_claims: int = 50) -> Dict[str, any]:
        """
        Cross-reference multiple claims against sources.
        
        Args:
            claims: List of claims to verify
            sources: List of source texts
            max_claims: Maximum claims to process (prevents runaway)
            
        Returns:
            Cross-reference results
        """
        verification_results = []
        for claim in claims[:max_claims]:  # Limit claims processed
            result = self.verify_claim(claim, sources[:20])  # Limit sources per claim
            verification_results.append(result)
        
        overall_confidence = sum(r["confidence"] for r in verification_results) / len(verification_results) if verification_results else 0.0
        
        return {
            "overall_confidence": overall_confidence,
            "verifications": verification_results,
            "high_confidence_claims": [r for r in verification_results if r["confidence"] >= 0.7],
            "low_confidence_claims": [r for r in verification_results if r["confidence"] < 0.5]
        }

