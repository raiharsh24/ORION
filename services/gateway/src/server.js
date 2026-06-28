import app from './app.js';
import { config } from './config/index.js';

// Start Server
app.listen(config.port, () => {
  console.log(`🚀 Gateway Service listening on port ${config.port} in [${config.nodeEnv}] mode`);
});
