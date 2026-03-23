# Implementation Plan: Personal Knowledge Brain

## Overview

This implementation plan extends the existing Deep Research Agent into a Personal Knowledge Brain by adding personal content ingestion, storage, and retrieval capabilities. All existing research functionality is preserved while adding new multi-modal processing and hybrid search features.

## Tasks

- [ ] 1. Set up personal knowledge storage foundation
  - Create SQLite database schema for documents and chunks
  - Implement KnowledgeStore service with basic CRUD operations
  - Add embedding storage and similarity search capabilities
  - _Requirements: 10.1, 10.2, 10.3, 10.4_

- [ ]* 1.1 Write property tests for KnowledgeStore
  - **Property 1: Storage round-trip consistency**
  - **Validates: Requirements 10.1**

- [ ] 2. Implement text processing pipeline
  - [ ] 2.1 Create TextProcessor service for plain text ingestion
    - Implement text chunking with semantic boundaries
    - Generate embeddings using sentence-transformers
    - Store processed content in KnowledgeStore
    - _Requirements: 4.1, 4.2, 4.3_

  - [ ]* 2.2 Write property tests for text processing
    - **Property 2: Text chunking preserves content**
    - **Validates: Requirements 9.1, 9.2**

  - [ ] 2.3 Add text ingestion API endpoint
    - Extend main.py with POST /knowledge/ingest/text
    - Implement input validation and rate limiting
    - Return processing results with chunk count
    - _Requirements: 4.1, 4.2_

- [ ] 3. Implement document processing pipeline
  - [ ] 3.1 Create DocumentProcessor service for PDF/Markdown files
    - Add PyMuPDF for PDF text extraction
    - Implement Markdown parsing with structure preservation
    - Create document-specific chunking strategies
    - _Requirements: 2.1, 2.2, 2.6_

  - [ ]* 3.2 Write property tests for document processing
    - **Property 3: Document parsing round-trip**
    - **Validates: Requirements 2.1, 2.2**

  - [ ] 3.3 Add document upload API endpoint
    - Extend main.py with POST /knowledge/ingest/document
    - Handle file uploads with size and format validation
    - Process documents asynchronously
    - _Requirements: 2.1, 2.2, 2.3_

- [ ] 4. Extend web content ingestion
  - [ ] 4.1 Extend WebSearchService for personal URL ingestion
    - Add ingest_personal_url method to existing service
    - Reuse existing content extraction and chunking logic
    - Store web content in personal knowledge base
    - _Requirements: 3.1, 3.2, 3.3_

  - [ ] 4.2 Add URL ingestion API endpoint
    - Extend main.py with POST /knowledge/ingest/url
    - Validate URL format and accessibility
    - Process web content for personal storage
    - _Requirements: 3.1, 3.4, 3.5_

- [ ] 5. Checkpoint - Basic ingestion complete
  - Ensure all ingestion endpoints work correctly
  - Verify content is stored and retrievable
  - Test with sample documents, text, and URLs
  - Ask the user if questions arise

- [ ] 6. Implement hybrid search engine
  - [ ] 6.1 Create HybridSearchEngine service
    - Implement semantic search using existing similarity logic
    - Add keyword search with full-text capabilities
    - Combine results using Reciprocal Rank Fusion algorithm
    - _Requirements: 6.1, 6.2, 7.1, 7.2_

  - [ ]* 6.2 Write property tests for hybrid search
    - **Property 4: Search result relevance ordering**
    - **Validates: Requirements 6.3, 7.2**

  - [ ] 6.3 Add personal knowledge search API endpoint
    - Extend main.py with POST /knowledge/search
    - Support personal-only and unified (personal + web) search modes
    - Return ranked results with similarity scores and metadata
    - _Requirements: 6.1, 6.2, 6.4, 6.5_

- [ ] 7. Implement enhanced research agent
  - [ ] 7.1 Create EnhancedResearchAgent extending existing ResearchAgent
    - Maintain all existing research functionality
    - Add unified_research method for personal + web search
    - Extend CoVe methodology for personal content synthesis
    - _Requirements: 6.1, 6.2_

  - [ ]* 7.2 Write integration tests for enhanced research
    - Test unified search combining personal and web results
    - Verify existing research functionality is preserved
    - _Requirements: 6.1, 6.2_

- [ ] 8. Add temporal query support
  - [ ] 8.1 Create TemporalParser service
    - Parse time expressions like "last month", "yesterday"
    - Convert to date ranges for filtering
    - Support both relative and absolute time queries
    - _Requirements: 8.1, 8.3, 8.5_

  - [ ] 8.2 Extend search with temporal filtering
    - Add temporal filtering to HybridSearchEngine
    - Implement time-based indexing for efficient queries
    - Support temporal constraints in search API
    - _Requirements: 8.2, 8.4, 8.5_

- [ ]* 8.3 Write property tests for temporal queries
  - **Property 5: Temporal filtering accuracy**
  - **Validates: Requirements 8.4, 8.5**

- [ ] 9. Add audio processing capability
  - [ ] 9.1 Create AudioProcessor service with Whisper integration
    - Implement audio transcription using OpenAI Whisper API
    - Create audio-specific chunking with timestamp preservation
    - Handle multiple audio formats (.mp3, .m4a, .wav, .ogg)
    - _Requirements: 1.1, 1.2, 1.5_

  - [ ]* 9.2 Write property tests for audio processing
    - **Property 6: Audio transcription consistency**
    - **Validates: Requirements 1.1, 1.2**

  - [ ] 9.3 Add audio upload API endpoint
    - Extend main.py with POST /knowledge/ingest/audio
    - Handle audio file uploads with format validation
    - Process audio files asynchronously
    - _Requirements: 1.1, 1.4, 1.5_

- [ ] 10. Implement content management features
  - [ ] 10.1 Add document listing API endpoint
    - Extend main.py with GET /knowledge/documents
    - Support filtering by modality and pagination
    - Return document metadata and statistics
    - _Requirements: 10.1, 10.3_

  - [ ] 10.2 Add document deletion API endpoint
    - Extend main.py with DELETE /knowledge/documents/{id}
    - Verify user ownership before deletion
    - Remove document and all associated chunks
    - _Requirements: 12.6_

  - [ ] 10.3 Extend cache statistics endpoint
    - Update GET /cache/stats to include personal knowledge metrics
    - Add processing pipeline statistics
    - Include storage usage and performance data
    - _Requirements: 11.3_

- [ ] 11. Final integration and testing
  - [ ] 11.1 Integration testing across all modalities
    - Test complete workflow: ingest → store → search → retrieve
    - Verify all content types work with unified search
    - Test error handling and edge cases
    - _Requirements: All requirements_

  - [ ]* 11.2 Write end-to-end property tests
    - **Property 7: Complete workflow consistency**
    - **Validates: Requirements 6.1, 10.4**

  - [ ] 11.3 Performance optimization and monitoring
    - Add performance monitoring for processing times
    - Optimize database queries and indexing
    - Implement caching for frequently accessed content
    - _Requirements: 11.1, 11.4, 11.5_

- [ ] 12. Final checkpoint - System validation
  - Ensure all tests pass and functionality works end-to-end
  - Verify existing research functionality is unchanged
  - Test system with realistic data volumes
  - Ask the user if questions arise

## Configuration Updates

- [ ] 13. Update configuration and dependencies
  - [ ] 13.1 Extend config.py with personal knowledge brain settings
    - Add database path, file size limits, supported formats
    - Configure embedding model and similarity thresholds
    - Set processing concurrency and timeout limits

  - [ ] 13.2 Update requirements.txt with new dependencies
    - Add sentence-transformers for embeddings
    - Add PyMuPDF for PDF processing
    - Add python-multipart for file uploads
    - Add openai for Whisper API (optional)

  - [ ] 13.3 Create database initialization script
    - SQL schema for documents and chunks tables
    - Indexes for performance optimization
    - Migration script for existing installations

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation and user feedback
- All new functionality extends existing services without disruption
- Property tests validate universal correctness properties
- Integration tests ensure system-wide functionality