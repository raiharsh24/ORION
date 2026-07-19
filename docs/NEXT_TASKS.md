# Next Tasks

Prioritized backlog queue for incoming AI sessions:

## Priority 1: FACS Verification & Handoff
- [ ] Complete automation logic inside `scripts/ai_session_manager.py`.
- [ ] Implement backend `FACSSubscriber` event listener integration.
- [ ] Create pytest unit tests verifying FACS subscriber state changes.
- [ ] Verify that running `ai_session_manager.py end` updates state documentation correctly.

## Priority 2: Semantic Memory & Search Enhancements
- [ ] Implement deep document chunks vectorization in `DocumentIndexer`.
- [ ] Optimize vector memory retrieval latency.
- [ ] Build user-facing workspace semantic explorer widget in HUD panel.

## Priority 3: Desktop HUD UI Customization
- [ ] Enhance Three.js overlay elements with modern styling.
- [ ] Integrate workspace status widget inside the Electron Command Center.
