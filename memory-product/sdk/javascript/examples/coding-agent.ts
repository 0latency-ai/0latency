/**
 * Coding agent example with project-specific memory
 * 
 * This example shows how to use 0Latency to maintain
 * context about a coding project across sessions.
 */

import { Memory } from '@0latency/sdk';

const memory = new Memory({ 
  apiKey: process.env.ZEROLATENCY_API_KEY || 'your-api-key-here' 
});

interface ProjectContext {
  projectId: string;
  userRequest: string;
}

async function codingAgent({ projectId, userRequest }: ProjectContext) {
  const agentId = `project-${projectId}`;
  
  console.log(`\n=== Coding Agent for Project: ${projectId} ===`);
  console.log(`Request: ${userRequest}\n`);

  // Recall project-specific knowledge
  const projectKnowledge = await memory.recall(
    `${userRequest} in the context of this codebase`,
    { agentId, limit: 5 }
  );

  console.log('Project knowledge:');
  if (projectKnowledge.memories && projectKnowledge.memories.length > 0) {
    projectKnowledge.memories.forEach((mem: any, i: number) => {
      console.log(`  ${i + 1}. ${mem.content} (confidence: ${mem.confidence || 'N/A'})`);
    });
  } else {
    console.log('  (no prior context found)');
  }

  return projectKnowledge;
}

async function storeProjectFact(projectId: string, fact: string, category: string) {
  console.log(`\nStoring fact: ${fact}`);
  
  await memory.add(fact, {
    agentId: `project-${projectId}`,
    metadata: {
      category,
      project: projectId,
      timestamp: Date.now()
    }
  });

  console.log('✓ Fact stored');
}

// Example usage
async function main() {
  const projectId = 'my-webapp';

  // Store some project facts
  await storeProjectFact(
    projectId,
    'User prefers functional programming style',
    'coding-style'
  );
  
  await storeProjectFact(
    projectId,
    'Backend API uses REST with Express.js',
    'architecture'
  );
  
  await storeProjectFact(
    projectId,
    'Database is PostgreSQL with Prisma ORM',
    'architecture'
  );

  // Query the agent
  await codingAgent({
    projectId,
    userRequest: 'Add a new API endpoint for user authentication'
  });

  // Different query
  await codingAgent({
    projectId,
    userRequest: 'What database are we using?'
  });
}

main().catch(console.error);
