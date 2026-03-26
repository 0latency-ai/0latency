// Test MCP tools locally
const tools = [
  { name: 'remember', args: { text: 'Test memory: Justin prefers TypeScript' } },
  { name: 'memory_search', args: { q: 'TypeScript' } },
  { name: 'memory_list', args: { limit: 5 } },
  { name: 'memory_recall', args: { query: 'programming preferences' } },
  { name: 'memory_graph_traverse', args: { memory_id: 'test-id', depth: 2 } },
  { name: 'memory_entities', args: { limit: 10 } },
  { name: 'memory_sentiment_summary', args: {} },
  { name: 'memory_by_entity', args: { entity_text: 'TypeScript' } },
  { name: 'memory_history', args: { memory_id: 'test-id' } },
  { name: 'seed_memories', args: { facts: ['Test fact 1', 'Test fact 2'] } },
];

console.log('MCP 0.1.4 Tool List:');
tools.forEach((tool, i) => {
  console.log(`${i + 1}. ${tool.name}`);
});
console.log(`\nTotal: ${tools.length} tools`);
