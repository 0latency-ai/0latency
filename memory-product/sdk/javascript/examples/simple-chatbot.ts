/**
 * Simple chatbot example with memory recall
 * 
 * This example shows how to use 0Latency to give a chatbot
 * memory of past conversations.
 */

import { Memory } from '@0latency/sdk';

const memory = new Memory({ 
  apiKey: process.env.ZEROLATENCY_API_KEY || 'your-api-key-here' 
});

async function chatWithMemory(userMessage: string, agentId: string = 'chatbot-1') {
  console.log(`\nUser: ${userMessage}`);

  // Recall relevant context from past conversations
  const context = await memory.recall(userMessage, {
    agentId,
    limit: 3
  });

  console.log('\nRecalled memories:');
  if (context.memories && context.memories.length > 0) {
    context.memories.forEach((mem: any, i: number) => {
      console.log(`  ${i + 1}. ${mem.content}`);
    });
  } else {
    console.log('  (no relevant memories found)');
  }

  // In a real chatbot, you'd pass this context to your LLM
  const response = `I remember our conversation! Here's what I know: ${
    context.memories?.map((m: any) => m.content).join(', ') || 'not much yet'
  }`;

  console.log(`\nAssistant: ${response}`);

  // Store the conversation for future recall
  await memory.extract([
    { role: 'user', content: userMessage },
    { role: 'assistant', content: response }
  ], { agentId });

  console.log('✓ Memory stored');
}

// Example conversation
async function main() {
  console.log('=== Simple Chatbot with 0Latency Memory ===\n');

  // First conversation - establish preferences
  await chatWithMemory('I love hiking in the mountains');
  
  // Later conversation - recall preferences
  await chatWithMemory('What outdoor activities should I try?');
}

main().catch(console.error);
