import { GoogleGenAI } from '@google/genai';

const apiKey = "AQ.Ab8RN6KmygMdQIrb60V6soJe5SchgwtMBUxBufQOro2imYdyrQ";
const ai = new GoogleGenAI({ apiKey: apiKey });

async function run() {
  try {
    const response = await ai.models.generateContent({
      model: 'gemini-1.5-flash',
      contents: 'Say hello in one word.',
    });
    console.log("SUCCESS:", response.text.trim());
  } catch (e) {
    console.error("FAILED:", e.message);
  }
}

run();
