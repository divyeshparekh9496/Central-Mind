#!/usr/bin/env python3
"""Generate PDF spec sheet."""
from fpdf import FPDF

class PDF(FPDF):
    def header(self):
        self.set_font('Helvetica', 'B', 12)
        self.set_text_color(102, 126, 234)
        self.cell(0, 10, 'Deep Research Agent - Technical Specification', align='C', new_x='LMARGIN', new_y='NEXT')
        self.ln(5)
    
    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(128)
        self.cell(0, 10, f'Page {self.page_no()}', align='C')
    
    def chapter_title(self, title):
        self.set_font('Helvetica', 'B', 14)
        self.set_text_color(118, 75, 162)
        self.cell(0, 10, title, new_x='LMARGIN', new_y='NEXT')
        self.set_draw_color(200)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(5)
    
    def section_title(self, title):
        self.set_font('Helvetica', 'B', 11)
        self.set_text_color(50)
        self.cell(0, 8, title, new_x='LMARGIN', new_y='NEXT')
        self.ln(2)
    
    def body_text(self, text):
        self.set_font('Helvetica', '', 10)
        self.set_text_color(60)
        self.multi_cell(0, 5, text)
        self.ln(3)
    
    def bullet_point(self, text):
        self.set_font('Helvetica', '', 10)
        self.set_text_color(60)
        self.cell(10, 5, chr(149))
        self.cell(0, 5, text, new_x='LMARGIN', new_y='NEXT')
    
    def add_table(self, headers, data):
        self.set_font('Helvetica', 'B', 9)
        self.set_fill_color(102, 126, 234)
        self.set_text_color(255)
        col_width = (self.w - 20) / len(headers)
        for header in headers:
            self.cell(col_width, 7, header, border=1, fill=True, align='C')
        self.ln()
        
        self.set_font('Helvetica', '', 9)
        self.set_text_color(60)
        fill = False
        for row in data:
            if fill:
                self.set_fill_color(245, 245, 245)
            else:
                self.set_fill_color(255, 255, 255)
            for item in row:
                self.cell(col_width, 6, str(item)[:30], border=1, fill=True)
            self.ln()
            fill = not fill
        self.ln(5)

# Create PDF
pdf = PDF()
pdf.set_auto_page_break(auto=True, margin=15)
pdf.add_page()

# Title
pdf.set_font('Helvetica', 'B', 24)
pdf.set_text_color(102, 126, 234)
pdf.cell(0, 15, 'Deep Research Agent', align='C', new_x='LMARGIN', new_y='NEXT')
pdf.set_font('Helvetica', '', 12)
pdf.set_text_color(100)
pdf.cell(0, 8, 'AI-Powered Research with Hallucination Reduction', align='C', new_x='LMARGIN', new_y='NEXT')
pdf.ln(10)

# Overview
pdf.chapter_title('Product Overview')
pdf.body_text('Deep Research Agent is an AI-powered research API with built-in hallucination reduction. It gathers information from multiple web sources, synthesizes responses using LLMs, and verifies facts through cross-referencing.')
pdf.ln(3)
pdf.section_title('Target Use Cases')
pdf.bullet_point('Mobile apps requiring factual research')
pdf.bullet_point('Wearable devices with voice queries')
pdf.bullet_point('Enterprise knowledge assistants')
pdf.bullet_point('Research automation tools')

# Architecture
pdf.add_page()
pdf.chapter_title('System Architecture')
pdf.body_text('The system consists of multiple layers working together:')
pdf.ln(3)
pdf.section_title('Layer Overview')
pdf.add_table(
    ['Layer', 'Components', 'Purpose'],
    [
        ['Client', 'Web UI, Mobile, API', 'User interface'],
        ['Gateway', 'FastAPI, Validators', 'Request handling'],
        ['Cache', 'Semantic Cache', 'Cost reduction'],
        ['Core', 'Research Agent', 'Orchestration'],
        ['Safeguards', 'Circuit Breaker, Retry', 'Reliability'],
    ]
)

# Hallucination Reduction
pdf.chapter_title('Hallucination Reduction System')
pdf.add_table(
    ['Technique', 'Description', 'Impact'],
    [
        ['Chain-of-Verification', 'Draft > Verify > Check > Final', '15-25% accuracy gain'],
        ['Multi-Source Verify', 'Cross-ref 3-8 sources', 'Reduces bias'],
        ['Confidence Scoring', '0-1 score per claim', 'Quantifies reliability'],
        ['Auto Refinement', 'Re-gen if conf < 0.7', 'Improves quality'],
        ['Source Grounding', 'LLM uses ONLY sources', 'Prevents fabrication'],
    ]
)

# Semantic Caching
pdf.chapter_title('Semantic Caching')
pdf.add_table(
    ['Feature', 'Specification'],
    [
        ['Match Types', 'Exact + Semantic similarity'],
        ['Similarity Threshold', '0.85 (configurable)'],
        ['TTL', '24 hours (configurable)'],
        ['Max Entries', '1,000 (configurable)'],
        ['Cost Savings', '50-90% on similar queries'],
        ['Latency', '<100ms cache hit vs 2-10s fresh'],
    ]
)

# Safeguards
pdf.add_page()
pdf.chapter_title('Production Safeguards')
pdf.add_table(
    ['Safeguard', 'Implementation', 'Purpose'],
    [
        ['Request Timeout', '120s max', 'Prevent hung requests'],
        ['Rate Limiting', '10 req/min per IP', 'Prevent abuse'],
        ['Concurrent Limit', 'Semaphore (5 max)', 'Control API costs'],
        ['Circuit Breaker', 'Disable after 5 fails', 'Graceful degradation'],
        ['Input Validation', 'Sanitize + limits', 'Security'],
        ['Retry w/ Backoff', '3 attempts, exp delay', 'Handle failures'],
    ]
)

# API Specification
pdf.chapter_title('API Specification')
pdf.section_title('Endpoints')
pdf.add_table(
    ['Method', 'Endpoint', 'Description'],
    [
        ['GET', '/', 'Web UI'],
        ['GET', '/health', 'Health check'],
        ['POST', '/research', 'Perform research'],
        ['GET', '/research', 'Research (query params)'],
        ['GET', '/research/stream', 'SSE streaming'],
        ['GET', '/cache/stats', 'Cache statistics'],
        ['GET', '/docs', 'Swagger UI'],
    ]
)

pdf.section_title('Research Depth Options')
pdf.add_table(
    ['Depth', 'Sources', 'Speed'],
    [
        ['quick', '3 sources', 'Fastest (5-15s)'],
        ['standard', '5 sources', 'Balanced (10-25s)'],
        ['deep', '8+ sources', 'Thorough (20-45s)'],
    ]
)

# Tech Stack
pdf.add_page()
pdf.chapter_title('Technology Stack')
pdf.add_table(
    ['Component', 'Technology', 'Purpose'],
    [
        ['Framework', 'FastAPI', 'Async API server'],
        ['LLM', 'Google Gemini 2.5', 'Response generation'],
        ['Web Search', 'DuckDuckGo', 'Source gathering'],
        ['HTML Parsing', 'BeautifulSoup', 'Content extraction'],
        ['HTTP Client', 'httpx (async)', 'Web requests'],
        ['Validation', 'Pydantic', 'Request models'],
        ['Retry Logic', 'Tenacity', 'Exponential backoff'],
        ['Vector Math', 'NumPy', 'Semantic similarity'],
    ]
)

# Configuration
pdf.chapter_title('Configuration')
pdf.section_title('Environment Variables')
pdf.set_font('Courier', '', 9)
pdf.set_text_color(60)
config_text = """GOOGLE_API_KEY=your_api_key
API_HOST=0.0.0.0
API_PORT=8000
CACHE_SIMILARITY_THRESHOLD=0.85
CACHE_TTL_HOURS=24
REQUEST_TIMEOUT_SECONDS=120
MAX_CONCURRENT_LLM_CALLS=5"""
pdf.multi_cell(0, 5, config_text)
pdf.ln(5)

# Performance
pdf.set_font('Helvetica', '', 10)
pdf.chapter_title('Performance Characteristics')
pdf.add_table(
    ['Metric', 'Value'],
    [
        ['Cache Hit Latency', '<100ms'],
        ['Fresh Query (Quick)', '5-15 seconds'],
        ['Fresh Query (Standard)', '10-25 seconds'],
        ['Fresh Query (Deep)', '20-45 seconds'],
        ['Memory Usage', '50-200MB'],
        ['Max Concurrent LLM', '5 calls'],
    ]
)

# Deployment
pdf.chapter_title('Deployment')
pdf.section_title('Quick Start')
pdf.set_font('Courier', '', 9)
deploy_text = """pip install -r requirements.txt
cp env.example .env
# Add GOOGLE_API_KEY to .env
python main.py
# Open http://localhost:8000"""
pdf.multi_cell(0, 5, deploy_text)
pdf.ln(5)

pdf.set_font('Helvetica', '', 10)
pdf.section_title('Production Checklist')
pdf.bullet_point('Set specific CORS origins')
pdf.bullet_point('Add authentication (API keys/OAuth)')
pdf.bullet_point('Use Redis for distributed caching')
pdf.bullet_point('Add monitoring/logging')
pdf.bullet_point('Configure SSL/TLS')

# Save
pdf.output('docs/Deep_Research_Agent_Spec_Sheet.pdf')
print('✅ PDF generated: docs/Deep_Research_Agent_Spec_Sheet.pdf')
