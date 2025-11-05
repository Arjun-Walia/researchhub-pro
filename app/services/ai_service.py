"""
AI Service for query enhancement and content analysis using OpenAI/Anthropic.
"""
import logging
from typing import List, Dict, Optional, Any
import openai
import requests
from anthropic import Anthropic
from tenacity import retry, stop_after_attempt, wait_exponential

from app.utils.exceptions import ExternalAPIError


logger = logging.getLogger(__name__)


class AIService:
    """
    AI-powered research assistant using OpenAI and Anthropic models.
    """
    
    def __init__(
        self,
        openai_key: Optional[str] = None,
        anthropic_key: Optional[str] = None,
        perplexity_key: Optional[str] = None,
        perplexity_base_url: Optional[str] = None
    ):
        """
        Initialize AI service.
        
        Args:
            openai_key: OpenAI API key
            anthropic_key: Anthropic API key
            perplexity_key: Perplexity API key
            perplexity_base_url: Base URL for Perplexity API
        """
        self.openai_key = openai_key
        self.anthropic_key = anthropic_key
        self.perplexity_key = perplexity_key
        self.perplexity_base_url = (perplexity_base_url or 'https://api.perplexity.ai').rstrip('/')
        self.perplexity_timeout = 12
        
        if openai_key:
            openai.api_key = openai_key
        
        if anthropic_key:
            self.anthropic = Anthropic(api_key=anthropic_key)
        else:
            self.anthropic = None
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def enhance_query(self, query: str, context: Optional[str] = None) -> str:
        """
        Enhance user query for better search results.
        
        Args:
            query: Original user query
            context: Additional context about research domain
            
        Returns:
            Enhanced query string
        """
        try:
            prompt = f"""You are a research assistant. Enhance this search query to make it more effective 
            for academic and professional research. Add relevant keywords and phrases while maintaining 
            the original intent.
            
            Original query: {query}
            {f'Context: {context}' if context else ''}
            
            Return only the enhanced query without explanation."""
            
            if self.perplexity_key:
                perplexity_query = self._perplexity_enhance_query(prompt)
                if perplexity_query:
                    return perplexity_query

            if self.openai_key:
                response = openai.ChatCompletion.create(
                    model="gpt-4",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                    max_tokens=150
                )
                return response.choices[0].message.content.strip()
            
            return query  # Fallback to original query
            
        except Exception as e:
            logger.error(f"Query enhancement failed: {str(e)}")
            return query
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def summarize_content(
        self,
        text: str,
        max_length: int = 200,
        style: str = "academic"
    ) -> str:
        """
        Generate summary of research content.
        
        Args:
            text: Text to summarize
            max_length: Maximum summary length in words
            style: Summary style (academic, casual, technical)
            
        Returns:
            Summary text
        """
        try:
            if not text or len(text.strip()) < 100:
                return text
            
            prompt = f"""Summarize this research content in a {style} style. 
            Keep it concise (max {max_length} words) while preserving key information.
            
            Content: {text[:4000]}  
            
            Summary:"""
            
            if self.openai_key:
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.5,
                    max_tokens=max_length * 2
                )
                return response.choices[0].message.content.strip()
            
            return text[:500] + "..."  # Fallback truncation
            
        except Exception as e:
            logger.error(f"Summarization failed: {str(e)}")
            return text[:500] + "..."
    
    def extract_key_points(self, text: str, num_points: int = 5) -> List[str]:
        """
        Extract key points from research content.
        
        Args:
            text: Source text
            num_points: Number of key points to extract
            
        Returns:
            List of key points
        """
        try:
            prompt = f"""Extract {num_points} key points from this research content. 
            Each point should be a concise, complete sentence.
            
            Content: {text[:4000]}
            
            Return as a numbered list."""
            
            if self.openai_key:
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.5,
                    max_tokens=500
                )
                
                # Parse numbered list
                content = response.choices[0].message.content.strip()
                points = []
                for line in content.split('\n'):
                    line = line.strip()
                    if line and (line[0].isdigit() or line.startswith('-') or line.startswith('•')):
                        # Remove numbering
                        point = line.lstrip('0123456789.-•) ').strip()
                        if point:
                            points.append(point)
                
                return points[:num_points]
            
            # Simple fallback
            sentences = text.split('.')[:num_points]
            return [s.strip() + '.' for s in sentences if len(s.strip()) > 20]
            
        except Exception as e:
            logger.error(f"Key point extraction failed: {str(e)}")
            return []
    
    def analyze_sentiment(self, text: str) -> Dict[str, Any]:
        """
        Analyze sentiment of research content.
        
        Args:
            text: Text to analyze
            
        Returns:
            Sentiment analysis results
        """
        try:
            prompt = f"""Analyze the sentiment and tone of this research content. 
            Rate it on these dimensions (0-1 scale):
            - Positivity (0=negative, 1=positive)
            - Objectivity (0=subjective, 1=objective)
            - Formality (0=casual, 1=formal)
            - Technical complexity (0=simple, 1=complex)
            
            Content: {text[:2000]}
            
            Return as JSON with these exact keys: positivity, objectivity, formality, complexity"""
            
            if self.openai_key:
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                    max_tokens=150
                )
                
                import json
                result = json.loads(response.choices[0].message.content.strip())
                return result
            
            # Default neutral scores
            return {
                'positivity': 0.5,
                'objectivity': 0.7,
                'formality': 0.6,
                'complexity': 0.5
            }
            
        except Exception as e:
            logger.error(f"Sentiment analysis failed: {str(e)}")
            return {'positivity': 0.5, 'objectivity': 0.5, 'formality': 0.5, 'complexity': 0.5}
    
    def extract_entities(self, text: str) -> Dict[str, List[str]]:
        """
        Extract named entities from text.
        
        Args:
            text: Source text
            
        Returns:
            Dictionary of entity types and their values
        """
        try:
            prompt = f"""Extract named entities from this text. Categorize them as:
            - People (names of individuals)
            - Organizations (companies, institutions)
            - Locations (places, countries, cities)
            - Topics (key concepts, technologies, theories)
            
            Content: {text[:3000]}
            
            Return as JSON with these keys: people, organizations, locations, topics"""
            
            if self.openai_key:
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                    max_tokens=400
                )
                
                import json
                result = json.loads(response.choices[0].message.content.strip())
                return result
            
            return {'people': [], 'organizations': [], 'locations': [], 'topics': []}
            
        except Exception as e:
            logger.error(f"Entity extraction failed: {str(e)}")
            return {'people': [], 'organizations': [], 'locations': [], 'topics': []}
    
    def generate_report(
        self,
        query: str,
        results: List[Dict[str, Any]],
        format_type: str = "executive"
    ) -> str:
        """
        Generate research report from search results.
        
        Args:
            query: Original research query
            results: List of search results
            format_type: Report format (executive, detailed, academic)
            
        Returns:
            Generated report text
        """
        try:
            # Compile results into context
            results_text = "\n\n".join([
                f"Source {i+1}: {r.get('title', 'Unknown')}\n{r.get('snippet', '')}"
                for i, r in enumerate(results[:10])
            ])
            
            prompt = f"""Generate a {format_type} research report based on these search results.
            
            Research Query: {query}
            
            Sources:
            {results_text}
            
            Create a well-structured report with:
            1. Executive Summary
            2. Key Findings
            3. Detailed Analysis
            4. Recommendations
            5. Sources
            
            Keep it professional and concise."""
            
            if self.openai_key:
                response = openai.ChatCompletion.create(
                    model="gpt-4",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                    max_tokens=2000
                )
                return response.choices[0].message.content.strip()
            
            # Fallback simple report
            report = f"# Research Report: {query}\n\n"
            report += f"## Summary\n\nFound {len(results)} relevant sources.\n\n"
            report += "## Key Sources\n\n"
            for i, r in enumerate(results[:5], 1):
                report += f"{i}. {r.get('title', 'Unknown')}\n"
            
            return report
            
        except Exception as e:
            logger.error(f"Report generation failed: {str(e)}")
            raise ExternalAPIError(f"AI report generation failed: {str(e)}")
    
    def suggest_related_queries(self, query: str, num_suggestions: int = 5) -> List[str]:
        """
        Suggest related research queries.
        
        Args:
            query: Original query
            num_suggestions: Number of suggestions
            
        Returns:
            List of related queries
        """
        try:
            prompt = f"""Based on this research query, suggest {num_suggestions} related queries 
            that would help expand the research.
            
            Original query: {query}
            
            Return only the queries, one per line, without numbering."""
            
            if self.openai_key:
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.8,
                    max_tokens=200
                )
                
                suggestions = response.choices[0].message.content.strip().split('\n')
                return [s.strip() for s in suggestions if s.strip()][:num_suggestions]
            
            return []
            
        except Exception as e:
            logger.error(f"Query suggestion failed: {str(e)}")
            return []
    
    def evaluate_source_quality(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate quality and credibility of a source.
        
        Args:
            result: Search result to evaluate
            
        Returns:
            Quality evaluation scores
        """
        try:
            title = result.get('title', '')
            snippet = result.get('snippet', '')
            url = result.get('url', '')
            
            prompt = f"""Evaluate this research source for quality and credibility (0-1 scale):
            
            Title: {title}
            URL: {url}
            Excerpt: {snippet[:500]}
            
            Rate these aspects:
            - Credibility (source trustworthiness)
            - Relevance (how relevant to research)
            - Recency (how current the information is)
            - Depth (how comprehensive)
            
            Return as JSON with keys: credibility, relevance, recency, depth, overall"""
            
            if self.openai_key:
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                    max_tokens=150
                )
                
                import json
                return json.loads(response.choices[0].message.content.strip())
            
            # Default moderate scores
            return {
                'credibility': 0.6,
                'relevance': 0.6,
                'recency': 0.5,
                'depth': 0.5,
                'overall': 0.55
            }
            
        except Exception as e:
            logger.error(f"Source evaluation failed: {str(e)}")
            return {'credibility': 0.5, 'relevance': 0.5, 'recency': 0.5, 'depth': 0.5, 'overall': 0.5}

    def _perplexity_enhance_query(self, prompt: str) -> Optional[str]:
        """Use Perplexity's chat completions to enhance a query if configured."""
        if not self.perplexity_key:
            return None

        endpoint = f"{self.perplexity_base_url}/chat/completions"
        payload = {
            "model": "llama-3.1-70b-instruct",
            "messages": [
                {
                    "role": "system",
                    "content": "You are a research assistant that rewrites search prompts for precision, recall, and clarity. Return only the improved query without commentary."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.3,
            "max_tokens": 200
        }

        headers = {
            'Authorization': f'Bearer {self.perplexity_key}',
            'Content-Type': 'application/json'
        }

        try:
            response = requests.post(endpoint, json=payload, headers=headers, timeout=self.perplexity_timeout)
        except requests.exceptions.RequestException as exc:
            logger.warning('Perplexity enhancement request failed: %s', exc)
            return None

        if response.status_code == 401:
            logger.warning('Perplexity API key rejected during enhancement.')
            return None

        if not response.ok:
            logger.warning('Perplexity enhancement returned %s: %s', response.status_code, response.text[:200])
            return None

        try:
            data = response.json()
        except ValueError:
            return None

        choices = data.get('choices') or []
        if not choices:
            return None

        message = choices[0].get('message') or {}
        content = message.get('content')

        if isinstance(content, list):
            content = ''.join(part.get('text', '') for part in content if isinstance(part, dict))

        if isinstance(content, str):
            content = content.strip()

        return content or None
