/**
 * Shared SSE/NDJSON stream parser for chat endpoints.
 * Parses newline-delimited JSON from ReadableStream and invokes callbacks.
 */

export type ChatStreamEventType = 'metadata' | 'clarify' | 'content' | 'done' | 'error';

export interface ChatStreamCallbacks {
  onMetadata?: (data: Record<string, unknown>) => void;
  onClarify?: (data: Record<string, unknown>) => void;
  onContent?: (data: { content?: string }) => void;
  onDone?: (data?: Record<string, unknown>) => void;
  onError?: (data?: Record<string, unknown>) => void;
  onBytesReceived?: () => void;
}

/**
 * Parse a chat stream (NDJSON) and invoke callbacks for each event type.
 * Resolves when the stream ends or is aborted.
 */
export async function parseChatStream(
  body: ReadableStream<Uint8Array>,
  callbacks: ChatStreamCallbacks,
  options?: { signal?: AbortSignal }
): Promise<void> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      if (options?.signal?.aborted) break;

      if (value) {
        callbacks.onBytesReceived?.();
        const chunk = decoder.decode(value, { stream: true });
        buffer += chunk;
        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';

        for (const line of lines) {
          if (!line.trim()) continue;
          try {
            const data = JSON.parse(line) as Record<string, unknown>;
            const type = data.type as string | undefined;

            if (type === 'clarify') {
              callbacks.onClarify?.(data);
            } else if (type === 'answer_metadata' || type === 'metadata') {
              callbacks.onMetadata?.(data);
            } else if (type === 'answer_token' || type === 'content') {
              callbacks.onContent?.(data as { content?: string });
            } else if (type === 'done') {
              callbacks.onDone?.(data);
            } else if (type === 'error') {
              callbacks.onError?.(data);
            }
          } catch (e) {
            console.error('[parseChatStream] Error parsing line:', e);
          }
        }
      }
    }

    // Handle remaining buffer
    const tail = buffer.trim();
    if (tail) {
      try {
        const data = JSON.parse(tail) as Record<string, unknown>;
        const type = data.type as string | undefined;

        if (type === 'clarify') {
          callbacks.onClarify?.(data);
        } else if (type === 'answer_metadata' || type === 'metadata') {
          callbacks.onMetadata?.(data);
        } else if (type === 'answer_token' || type === 'content') {
          callbacks.onContent?.(data as { content?: string });
        } else if (type === 'done') {
          callbacks.onDone?.(data);
        } else if (type === 'error') {
          callbacks.onError?.(data);
        }
      } catch (e) {
        console.error('[parseChatStream] Error parsing tail:', e);
      }
    }
  } finally {
    reader.releaseLock();
  }
}
