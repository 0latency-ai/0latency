/**
 * Async extraction example with polling
 * 
 * This example shows how to use the extract() method
 * to process conversations in the background.
 */

import { Memory } from '@0latency/sdk';

const memory = new Memory({ 
  apiKey: process.env.ZEROLATENCY_API_KEY || 'your-api-key-here' 
});

async function extractAndPoll(
  conversation: Array<{ role: string; content: string }>,
  agentId: string
) {
  console.log('\n=== Starting async extraction ===');
  console.log(`Conversation length: ${conversation.length} messages`);

  // Start extraction job
  const { job_id } = await memory.extract(conversation, { agentId });
  console.log(`Job created: ${job_id}`);

  // Poll for completion
  let attempts = 0;
  const maxAttempts = 30;
  
  while (attempts < maxAttempts) {
    await new Promise(resolve => setTimeout(resolve, 1000)); // Wait 1 second
    
    const status = await memory.extractStatus(job_id);
    console.log(`Attempt ${attempts + 1}: Status = ${status.state || 'unknown'}`);
    
    if (status.state === 'completed') {
      console.log('\n✓ Extraction complete!');
      console.log('Result:', JSON.stringify(status, null, 2));
      return status;
    }
    
    if (status.state === 'failed') {
      console.error('\n✗ Extraction failed!');
      console.error('Error:', status.error);
      throw new Error('Extraction failed');
    }
    
    attempts++;
  }

  throw new Error('Extraction timeout - exceeded maximum attempts');
}

// Example conversation to extract
async function main() {
  const conversation = [
    {
      role: 'user',
      content: 'I really love mountain biking on weekends. Been doing it for 5 years now.'
    },
    {
      role: 'assistant',
      content: 'That\'s wonderful! Mountain biking is a great way to stay active and enjoy nature.'
    },
    {
      role: 'user',
      content: 'Yeah, my favorite trail is the one near Boulder. It has amazing views.'
    },
    {
      role: 'assistant',
      content: 'Boulder has some incredible trails! The scenery there is breathtaking.'
    },
    {
      role: 'user',
      content: 'I also enjoy photography while I\'m out there. Nature photography is my hobby.'
    },
    {
      role: 'assistant',
      content: 'Combining biking with photography sounds like a perfect combination!'
    }
  ];

  try {
    await extractAndPoll(conversation, 'user-123');
  } catch (error) {
    console.error('Error:', error);
  }
}

main().catch(console.error);
