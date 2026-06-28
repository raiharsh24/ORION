import { ResponseFormatter } from '../../../../src/ai/response/ResponseFormatter.js';

/**
 * Global Express Error Handler.
 * Formats errors consistently using the existing ResponseFormatter utility.
 */
export const errorHandler = (err, req, res, next) => {
  console.error("Unhandled gateway error:", err);
  
  const status = err.status || 500;
  
  // Format the error into the standardized ResponseFormatter envelop
  const formattedError = ResponseFormatter.formatError(
    err.message || "An unexpected error occurred.",
    "gateway"
  );
  
  res.status(status).json(formattedError);
};
