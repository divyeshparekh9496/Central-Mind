/**
 * Example usage of the Research Agent API in JavaScript/Node.js
 */

const API_BASE_URL = 'http://localhost:8000';

/**
 * Query the research agent API
 * @param {string} query - Research query
 * @param {string} depth - Research depth: 'quick', 'standard', or 'deep'
 * @returns {Promise<Object>} Research result
 */
async function researchQuery(query, depth = 'standard') {
  const response = await fetch(`${API_BASE_URL}/research`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      query: query,
      depth: depth
    })
  });

  if (!response.ok) {
    throw new Error(`API Error: ${response.status} - ${await response.text()}`);
  }

  return await response.json();
}

/**
 * Pretty print research results
 * @param {Object} result - Research result object
 */
function printResearchResult(result) {
  console.log('\n' + '='.repeat(80));
  console.log(`QUERY: ${result.query}`);
  console.log('='.repeat(80));
  console.log(`\nRESPONSE:\n${result.response}`);
  console.log('\n' + '-'.repeat(80));
  console.log(`Confidence Score: ${(result.confidence_score * 100).toFixed(2)}%`);
  console.log(`Verified: ${result.verification.verified}`);
  console.log(`Sources Checked: ${result.verification.total_sources}`);
  console.log(`Supporting Sources: ${result.verification.supporting_sources}`);
  console.log('\nCITATIONS:');
  result.citations.forEach(citation => {
    console.log(`  [${citation.id}] ${citation.title}`);
    console.log(`      ${citation.url}`);
  });
  console.log('='.repeat(80) + '\n');
}

// Example usage
async function main() {
  const queries = [
    'What are the latest developments in artificial intelligence?',
    'How does quantum computing work?',
    'What are the health benefits of meditation?'
  ];

  for (const query of queries) {
    try {
      console.log(`\n🔍 Researching: ${query}`);
      const result = await researchQuery(query, 'standard');
      printResearchResult(result);
    } catch (error) {
      console.error(`❌ Error: ${error.message}`);
    }
  }
}

// Run if executed directly
if (require.main === module) {
  main().catch(console.error);
}

module.exports = { researchQuery, printResearchResult };

