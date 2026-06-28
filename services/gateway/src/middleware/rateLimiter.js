import rateLimit from 'express-rate-limit';

/**
 * Basic rate limiter middleware.
 * Restricts requests per IP to 100 requests per 15 minutes window.
 */
export const limiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 100, // Limit each IP to 100 requests per window
  standardHeaders: true, // Return rate limit info in the `RateLimit-*` headers
  legacyHeaders: false, // Disable the `X-RateLimit-*` headers
  message: {
    success: false,
    response: "Too many requests from this IP, please try again later.",
    timestamp: new Date().toISOString()
  }
});
