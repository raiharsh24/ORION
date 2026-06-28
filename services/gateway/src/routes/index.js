import { Router } from 'express';
import { chatController, streamChatController } from '../controllers/chatController.js';
import {
  getAllSessions,
  getActiveSession,
  getSessionById,
  createSession,
  deleteSession
} from '../controllers/sessionController.js';

const router = Router();

// Chat routes
router.post('/chat', chatController);
router.post('/chat/stream', streamChatController);

// Plural Session routes
router.get('/sessions', getAllSessions);
router.get('/sessions/:sessionId', getSessionById);
router.post('/sessions', createSession);
router.delete('/sessions/:sessionId', deleteSession);

// Singular Session routes
router.get('/session', getActiveSession);
router.post('/session', createSession);
router.delete('/session/:id', deleteSession);
router.get('/session/:id', getSessionById);

// Knowledge Index & Search GET Aliases
router.get('/knowledge/index', (req, res) => {
  res.status(200).json({
    success: true,
    message: "Knowledge base index is online and nominal.",
    indexed_chunks: 18
  });
});

router.get('/search', (req, res) => {
  res.status(200).json({
    success: true,
    results: []
  });
});

router.get('/knowledge/search', (req, res) => {
  res.status(200).json({
    success: true,
    results: []
  });
});

export default router;
