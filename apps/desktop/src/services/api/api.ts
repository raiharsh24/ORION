export interface RequestOptions extends RequestInit {
  timeout?: number;
  retries?: number;
  retryDelay?: number;
}

const DEFAULT_TIMEOUT = 5000; // 5 seconds
const DEFAULT_RETRIES = 2;
const DEFAULT_RETRY_DELAY = 1000;

export async function apiFetch<T>(url: string, options: RequestOptions = {}): Promise<T> {
  const { timeout = DEFAULT_TIMEOUT, retries = DEFAULT_RETRIES, retryDelay = DEFAULT_RETRY_DELAY, ...fetchOptions } = options;
  
  let attempt = 0;
  
  while (true) {
    const controller = new AbortController();
    const id = setTimeout(() => controller.abort(), timeout);
    
    try {
      const response = await fetch(url, {
        ...fetchOptions,
        signal: controller.signal,
        headers: {
          'Content-Type': 'application/json',
          ...fetchOptions.headers,
        },
      });
      
      clearTimeout(id);
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      return (await response.json()) as T;
    } catch (error: any) {
      clearTimeout(id);
      
      const isTimeout = error.name === 'AbortError';
      const isNetworkError = error.message && (
        error.message.includes('failed to fetch') || 
        error.message.includes('NetworkError') || 
        error.message.includes('Failed to fetch')
      );
      
      const shouldRetry = attempt < retries && (isTimeout || isNetworkError);
      
      if (shouldRetry) {
        attempt++;
        await new Promise((resolve) => setTimeout(resolve, retryDelay * attempt));
        continue;
      }
      
      throw error;
    }
  }
}
