"""Deep research agent with Gemini LLM integration and hallucination reduction."""
import asyncio
from typing import Dict, List, Optional, Any
import google.generativeai as genai
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from config import Config
from services.web_search import WebSearchService
from services.fact_checker import FactChecker
from services.semantic_cache import SemanticCache
from services.safeguards import CircuitBreaker, create_llm_semaphore


class ResearchAgent:
    """Deep research agent that uses Gemini with hallucination reduction."""
    
    def __init__(self):
        # Configure Gemini
        genai.configure(api_key=Config.GOOGLE_API_KEY)
        self.model = genai.GenerativeModel(
            model_name=Config.GEMINI_MODEL,
            generation_config={
                "temperature": Config.TEMPERATURE,
                "max_output_tokens": Config.MAX_TOKENS,
            }
        )
        
        self.web_search = WebSearchService()
        self.fact_checker = FactChecker()
        self.semantic_cache = SemanticCache(
            similarity_threshold=Config.CACHE_SIMILARITY_THRESHOLD,
            ttl_hours=Config.CACHE_TTL_HOURS
        )
        self.model_name = Config.GEMINI_MODEL
        
        # Safeguards
        self.llm_semaphore = create_llm_semaphore(Config.MAX_CONCURRENT_LLM_CALLS)
        self.refinement_circuit_breaker = CircuitBreaker(
            failure_threshold=Config.CIRCUIT_BREAKER_THRESHOLD
        )
    
    async def research(self, query: str, depth: str = "standard") -> Dict[str, Any]:
        """
        Perform deep research on a query with fact-checking.
        
        Args:
            query: Research query
            depth: Research depth ("quick", "standard", "deep")
            
        Returns:
            Research results with citations and verification
        """
        # Step 0: Check semantic cache first
        cached = await self.semantic_cache.get(query, depth)
        if cached:
            cached["metadata"]["cache_hit"] = True
            cached["metadata"]["cache_type"] = cached.get("cache_type", "exact")
            return cached
        
        # Step 1: Gather information from multiple sources (PARALLEL)
        search_results = await self._gather_sources_parallel(query, depth)
        
        # Step 2: Extract content from sources (already parallel)
        source_contents = await self._extract_source_contents(search_results)
        
        # Step 3: Generate research response with Claude using CoVe
        research_response = await self._generate_cove_response(
            query, search_results, source_contents
        )
        
        # Step 4: Fact-check the response
        verification = await self._verify_response(
            research_response, source_contents
        )
        
        # Step 5: Refine response if needed (MAX 1 refinement to prevent loops)
        if (verification["overall_confidence"] < Config.VERIFICATION_THRESHOLD and 
            self.refinement_circuit_breaker.should_allow_operation()):
            try:
                research_response = await self._refine_response(
                    query, research_response, verification, source_contents
                )
                # Re-verify once, but don't refine again regardless of result
                verification = await self._verify_response(
                    research_response, source_contents
                )
                verification["refinement_applied"] = True
                self.refinement_circuit_breaker.record_success()
            except Exception as e:
                self.refinement_circuit_breaker.record_failure()
                # Continue with original response if refinement fails
                verification["refinement_error"] = str(e)
        
        result = {
            "query": query,
            "response": research_response["content"],
            "citations": research_response["citations"],
            "sources": search_results,
            "verification": verification,
            "confidence_score": verification["overall_confidence"],
            "metadata": {
                "model": self.model_name,
                "sources_checked": len(source_contents),
                "depth": depth,
                "cache_hit": False
            }
        }
        
        # Cache the result for future similar queries
        await self.semantic_cache.set(query, depth, result)
        
        return result
    
    async def _gather_sources(self, query: str, depth: str) -> List[Dict[str, str]]:
        """Gather sources from web search (legacy sequential method)."""
        return await self._gather_sources_parallel(query, depth)
    
    async def _gather_sources_parallel(self, query: str, depth: str) -> List[Dict[str, str]]:
        """Gather sources from web search with parallel execution."""
        max_results = {
            "quick": 3,
            "standard": 5,
            "deep": 8
        }.get(depth, 5)
        
        # Build search query variations
        search_queries = [query]
        if depth in ["standard", "deep"]:
            search_queries.extend([
                f"{query} facts",
                f"{query} research"
            ])
        if depth == "deep":
            search_queries.append(f"{query} latest news")
        
        # Execute ALL searches in parallel
        tasks = [
            self.web_search.search(q, max_results=max_results) 
            for q in search_queries
        ]
        results_lists = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Flatten and dedupe results
        all_results = []
        for results in results_lists:
            if isinstance(results, list):
                all_results.extend(results)
        
        seen_urls = set()
        unique_results = []
        for result in all_results:
            if result["url"] not in seen_urls:
                seen_urls.add(result["url"])
                unique_results.append(result)
        
        return unique_results[:max_results * len(search_queries)]
    
    async def _extract_source_contents(self, search_results: List[Dict[str, str]]) -> List[str]:
        """Extract content from source URLs with snippet fallback."""
        tasks = [self.web_search.fetch_content(result["url"]) for result in search_results]
        contents = await asyncio.gather(*tasks, return_exceptions=True)
        
        valid_contents = []
        for i, content in enumerate(contents):
            if isinstance(content, str) and len(content) > 100:
                valid_contents.append(content)
            elif i < len(search_results) and search_results[i].get("snippet"):
                # Fallback to snippet if full extraction fails
                valid_contents.append(f"Summary: {search_results[i]['snippet']}")
        
        return valid_contents
    
    async def _generate_research_response(
        self, 
        query: str, 
        sources: List[Dict[str, str]], 
        source_contents: List[str]
    ) -> Dict[str, Any]:
        """Generate research response using Claude (legacy method)."""
        return await self._generate_cove_response(query, sources, source_contents)
    
    async def _generate_cove_response(
        self, 
        query: str, 
        sources: List[Dict[str, str]], 
        source_contents: List[str]
    ) -> Dict[str, Any]:
        """
        Generate research response using Chain-of-Verification (CoVe).
        
        CoVe process:
        1. Draft initial response
        2. Generate verification questions
        3. Answer verification questions from sources
        4. Produce final verified response
        """
        # Prepare source context
        source_context = ""
        citations = []
        
        for i, source in enumerate(sources[:len(source_contents)]):
            if i < len(source_contents):
                source_context += f"\n\n[Source {i+1}]: {source['title']}\nURL: {source['url']}\nContent: {source_contents[i][:1500]}"
                citations.append({
                    "id": i+1,
                    "title": source["title"],
                    "url": source["url"]
                })
        
        # CoVe System Prompt - single call that performs all verification steps
        cove_system_prompt = """You are a precise research assistant using Chain-of-Verification (CoVe) methodology.

Your task is to provide accurate, well-researched information by following this EXACT process:

## STEP 1: DRAFT
Write an initial response to the query using ONLY the provided sources. Include [Source X] citations.

## STEP 2: VERIFY
List 3-5 specific verification questions about factual claims in your draft. Focus on:
- Numbers, dates, statistics
- Names, entities, relationships
- Cause-effect claims
- Comparative statements

## STEP 3: CHECK
For EACH verification question, search the provided sources and answer:
- "VERIFIED: [evidence from Source X]" if found
- "UNVERIFIED: not found in sources" if not found
- "CONFLICTING: Source X says... but Source Y says..." if contradictory

## STEP 4: FINAL RESPONSE
Write your final response incorporating verification results:
- Keep only VERIFIED claims with citations
- Remove or clearly mark UNVERIFIED claims as uncertain
- Note any CONFLICTING information from sources
- Add a brief confidence note at the end

CRITICAL RULES:
- ONLY use information explicitly stated in provided sources
- NEVER fabricate facts, numbers, dates, or names
- If information is missing, say "This information is not available in the provided sources"
- Always cite sources using [Source X] format

OUTPUT FORMAT:
Return ONLY the final verified response (Step 4). Do not include the intermediate steps in your output."""

        user_prompt = f"""Research Query: {query}

Available Sources:
{source_context}

Apply the Chain-of-Verification process internally, then provide your final verified response with citations."""

        # Combine system and user prompt for Gemini
        full_prompt = f"{cove_system_prompt}\n\n{user_prompt}"

        try:
            content = await self._call_gemini_with_retry(full_prompt)
            
            return {
                "content": content,
                "citations": citations
            }
            
        except Exception as e:
            return {
                "content": f"Error generating response: {str(e)}",
                "citations": citations
            }
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((Exception,))
    )
    async def _call_gemini_with_retry(self, prompt: str) -> str:
        """Call Gemini with retry logic and concurrency control."""
        async with self.llm_semaphore:  # Limit concurrent calls
            try:
                # Run sync Gemini call in thread pool
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: self.model.generate_content(prompt)
                )
                return response.text if response.text else ""
            except Exception as e:
                print(f"Gemini API error: {type(e).__name__}: {e}")
                raise
    
    async def _verify_response(
        self, 
        response: Dict[str, Any], 
        source_contents: List[str]
    ) -> Dict[str, Any]:
        """Verify the response against source contents."""
        # Extract text content from response dict
        response_text = response.get("content", "") if isinstance(response, dict) else str(response)
        
        # Extract claims from response
        claims = self.fact_checker.extract_claims(response_text)
        
        if not claims:
            return {
                "overall_confidence": 0.5,
                "verifications": [],
                "high_confidence_claims": [],
                "low_confidence_claims": []
            }
        
        # Verify each claim
        claim_texts = [claim["claim"] for claim in claims]
        verification = self.fact_checker.cross_reference(claim_texts, source_contents)
        
        return verification
    
    async def _refine_response(
        self,
        query: str,
        original_response: Dict[str, Any],
        verification: Dict[str, Any],
        source_contents: List[str]
    ) -> Dict[str, Any]:
        """Refine response based on verification results."""
        
        low_confidence_claims = [v["claim"] for v in verification["low_confidence_claims"]]
        
        if not low_confidence_claims:
            return original_response
        
        refinement_prompt = f"""You are refining a research response to improve accuracy. Follow the instructions precisely.

The following claims in the research response have low confidence scores and may not be well-supported by sources:

Low Confidence Claims:
{chr(10).join(f"- {claim}" for claim in low_confidence_claims[:5])}

Original Response:
{original_response['content']}

Please revise the response to:
1. Remove or clearly mark uncertain claims
2. Only include information that can be verified from sources
3. Add disclaimers where information is incomplete
4. Maintain citations for all factual statements"""
        
        try:
            refined_content = await self._call_gemini_with_retry(refinement_prompt)
            
            return {
                "content": refined_content,
                "citations": original_response["citations"]
            }
            
        except Exception as e:
            return original_response

