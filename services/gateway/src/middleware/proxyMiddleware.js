import http from 'http';

/**
 * Creates an Express reverse proxy handler targeting the Python FastAPI core backend.
 * @param {string} targetUrl - Python core service target URL.
 * @returns {Function} Express middleware.
 */
export const pythonProxy = (targetUrl = 'http://localhost:8000') => {
  const target = new URL(targetUrl);

  return (req, res, next) => {
    // Retain full URL and query path
    const path = req.originalUrl;

    const options = {
      protocol: target.protocol,
      hostname: target.hostname,
      port: target.port,
      method: req.method,
      path: path,
      headers: {
        ...req.headers,
        host: target.host // Override host header to match target URL
      }
    };

    // Create the HTTP request to forward to Python service
    const proxyReq = http.request(options, (proxyRes) => {
      // Forward status code and response headers
      res.writeHead(proxyRes.statusCode, proxyRes.headers);
      // Pipe the response stream chunk-by-chunk
      proxyRes.pipe(res);
    });

    proxyReq.on('error', (err) => {
      console.error(`Reverse-proxy connection error for path '${path}':`, err.message);
      res.status(502).json({
        success: false,
        error: `Python core system service at port 8000 is unreachable.`
      });
    });

    // Pipe the request body chunk-by-chunk into the proxy request
    req.pipe(proxyReq);
  };
};
