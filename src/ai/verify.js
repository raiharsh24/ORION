import { OrionEngine } from './index.js';
import { BaseProvider } from './providers/BaseProvider.js';
import { GeminiProvider } from './providers/GeminiProvider.js';

// Simple assertion helper
function assert(condition, message) {
  if (!condition) {
    console.error(`❌ Assertion Failed: ${message}`);
    process.exit(1);
  }
}

async function runVerification() {
  console.log("🚀 Starting Conversation Engine verification tests...");

  const engine = new OrionEngine({
    context: { maxMessageCount: 4, maxTokenLimit: 100 },
    prompt: { systemPrompt: "You are ORION Verification Bot." }
  });

  const sessionId = "test-session-123";

  // Test 1: Provider Factory registration check
  console.log("\n🧪 Test 1: Factory registration check...");
  assert(engine.providerFactory.hasProvider("gemini") === true, "Provider factory must register 'gemini'");
  assert(engine.providerFactory.hasProvider("mock") === true, "Provider factory must register 'mock'");
  console.log("   ✓ Success: 'gemini' and 'mock' are registered in the factory.");

  // Test 2: GeminiProvider instantiation
  console.log("\n🧪 Test 2: GeminiProvider instantiation check...");
  const provider = engine.providerFactory.createProvider("gemini");
  assert(provider instanceof GeminiProvider, "Created provider must be an instance of GeminiProvider");
  assert(provider.modelName === "gemini-1.5-flash", "Model name should default to gemini-1.5-flash");
  console.log("   ✓ Success: GeminiProvider is instantiated correctly.");

  // Test 3: API Key check and execution
  console.log("\n🧪 Test 3: Environment API Key check...");
  const apiKey = process.env.GEMINI_API_KEY || "";
  console.log(`   API Key available in env: ${apiKey ? "YES (hidden)" : "NO"}`);
  
  if (!apiKey) {
    console.warn("⚠️  Skipping live API call because GEMINI_API_KEY is not defined.");
    console.log("\nProvider: gemini");
    console.log("Model: gemini-1.5-flash");
    console.log("Tokens: [Skipped, missing API key]");
    console.log("First streamed chunk: [Skipped, missing API key]");
    console.log("\n🎉 ALL LOCAL CODE INTEGRATION TESTS PASSED SUCCESSFULLY!");
    return;
  }

  // If API key is present, perform end-to-end live check
  try {
    console.log("\n🧪 Test 4: Live Gemini prompt execution...");
    const res = await engine.chat(sessionId, "Hello");
    assert(res.success === true, "Response should be successful");
    
    console.log("\nProvider: " + res.provider);
    console.log("Model: " + res.model);
    console.log("Tokens: " + JSON.stringify(res.usage));
    
    console.log("\n🧪 Test 5: Live Gemini streaming execution...");
    const stream = await engine.streamChat(sessionId, "Hello");
    let firstChunk = null;
    for await (const chunk of stream) {
      if (!firstChunk) firstChunk = chunk;
    }
    console.log("First streamed chunk: " + (firstChunk || "None"));
    console.log("\n🎉 ALL TESTS PASSED SUCCESSFULLY! The live Gemini connection is functional.");
  } catch (err) {
    console.error("❌ Live API call failed with exception:", err.message);
    process.exit(1);
  }
}

runVerification().catch(err => {
  console.error("❌ Verification Failed with exception:", err);
  process.exit(1);
});
