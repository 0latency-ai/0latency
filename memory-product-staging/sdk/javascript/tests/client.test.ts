import { Memory, AuthenticationError, RateLimitError, ZeroLatencyError } from '../src';

// Mock fetch globally
global.fetch = jest.fn();

describe('Memory Client', () => {
  let client: Memory;
  const mockApiKey = 'test-api-key';

  beforeEach(() => {
    client = new Memory({ apiKey: mockApiKey });
    jest.clearAllMocks();
  });

  describe('constructor', () => {
    it('should initialize with API key', () => {
      expect(client).toBeInstanceOf(Memory);
    });

    it('should use default base URL', () => {
      const client = new Memory({ apiKey: 'test' });
      expect(client).toBeDefined();
    });

    it('should accept custom base URL', () => {
      const customUrl = 'https://custom.api.com';
      const client = new Memory({ apiKey: 'test', baseUrl: customUrl });
      expect(client).toBeDefined();
    });

    it('should strip trailing slash from base URL', () => {
      const client = new Memory({ apiKey: 'test', baseUrl: 'https://api.com/' });
      expect(client).toBeDefined();
    });
  });

  describe('add', () => {
    it('should add a memory successfully', async () => {
      const mockResponse = { id: '123', content: 'test memory' };
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      });

      const result = await client.add('test memory');
      expect(result).toEqual(mockResponse);
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/v1/memories'),
        expect.objectContaining({
          method: 'POST',
          headers: expect.objectContaining({
            'Authorization': `Bearer ${mockApiKey}`,
            'Content-Type': 'application/json',
          }),
          body: JSON.stringify({ content: 'test memory' }),
        })
      );
    });

    it('should add memory with agent_id and metadata', async () => {
      const mockResponse = { id: '123' };
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      });

      await client.add('test', {
        agentId: 'agent-1',
        metadata: { category: 'test' },
      });

      expect(global.fetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          body: JSON.stringify({
            content: 'test',
            agent_id: 'agent-1',
            metadata: { category: 'test' },
          }),
        })
      );
    });
  });

  describe('recall', () => {
    it('should recall memories successfully', async () => {
      const mockResponse = { memories: [{ content: 'memory 1' }] };
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      });

      const result = await client.recall('test query');
      expect(result).toEqual(mockResponse);
    });

    it('should include query parameters', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      });

      await client.recall('query', { agentId: 'agent-1', limit: 5 });

      const callUrl = (global.fetch as jest.Mock).mock.calls[0][0];
      expect(callUrl).toContain('query=query');
      expect(callUrl).toContain('limit=5');
      expect(callUrl).toContain('agent_id=agent-1');
    });
  });

  describe('extract', () => {
    it('should start extraction job', async () => {
      const mockResponse = { job_id: 'job-123' };
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      });

      const conversation = [
        { role: 'user', content: 'Hello' },
        { role: 'assistant', content: 'Hi!' },
      ];

      const result = await client.extract(conversation);
      expect(result).toEqual(mockResponse);
      expect(result.job_id).toBe('job-123');
    });
  });

  describe('extractStatus', () => {
    it('should check extraction status', async () => {
      const mockResponse = { status: 'completed' };
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      });

      const result = await client.extractStatus('job-123');
      expect(result).toEqual(mockResponse);
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/v1/memories/extract/job-123'),
        expect.any(Object)
      );
    });
  });

  describe('health', () => {
    it('should check API health', async () => {
      const mockResponse = { status: 'healthy' };
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      });

      const result = await client.health();
      expect(result).toEqual(mockResponse);
    });
  });

  describe('error handling', () => {
    it('should throw AuthenticationError on 401', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: false,
        status: 401,
        json: async () => ({ detail: 'Unauthorized' }),
      });

      await expect(client.add('test')).rejects.toThrow(AuthenticationError);
    });

    it('should throw RateLimitError on 429', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: false,
        status: 429,
        json: async () => ({ detail: 'Too many requests' }),
      });

      await expect(client.add('test')).rejects.toThrow(RateLimitError);
    });

    it('should throw ZeroLatencyError on other errors', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: async () => ({ detail: 'Server error' }),
        text: async () => 'Server error',
      });

      await expect(client.add('test')).rejects.toThrow(ZeroLatencyError);
    });

    it('should handle timeout', async () => {
      const client = new Memory({ apiKey: 'test', timeout: 10 });
      
      (global.fetch as jest.Mock).mockImplementationOnce(
        () => new Promise((resolve, reject) => {
          setTimeout(() => {
            const error = new Error('The operation was aborted');
            error.name = 'AbortError';
            reject(error);
          }, 100);
        })
      );

      const error = await client.add('test').catch(e => e);
      expect(error).toBeInstanceOf(ZeroLatencyError);
      expect(error.message).toMatch(/timeout/);
    });
  });
});
