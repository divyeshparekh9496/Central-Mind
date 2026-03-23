#!/bin/bash
# Example cURL commands for the Research Agent API

API_URL="http://localhost:8000"

echo "=== Health Check ==="
curl -X GET "${API_URL}/health"
echo -e "\n\n"

echo "=== Research Query (POST) ==="
curl -X POST "${API_URL}/research" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are the latest developments in artificial intelligence?",
    "depth": "standard"
  }'
echo -e "\n\n"

echo "=== Research Query (GET) ==="
curl -X GET "${API_URL}/research?query=What%20is%20quantum%20computing&depth=standard"
echo -e "\n\n"

echo "=== Quick Research ==="
curl -X POST "${API_URL}/research" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is climate change?",
    "depth": "quick"
  }'
echo -e "\n\n"

echo "=== Deep Research ==="
curl -X POST "${API_URL}/research" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are the health benefits of exercise?",
    "depth": "deep"
  }'
echo -e "\n"

