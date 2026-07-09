import { describe, it, expect } from 'vitest';
import { GraphAnalytics } from './GraphAnalytics';
import type { GraphNode, GraphLink } from '../types';

describe('GraphAnalytics Engine Verification', () => {
  it('correctly audits degree, components, cycles, bridges, and shortest path on a synthetic graph', () => {
    // 1. Setup Synthetic Graph
    // Cycle 1: A -> B -> C -> A
    // Connection: C -> D
    // Cycle 2: D -> E -> F -> D
    // Orphan: G
    const nodes: GraphNode[] = [
      { id: 'A', title: 'Node A', description: '', type: 'code', category: 'Dev', tags: [], importance: 0.5, status: 'HEALTHY', createdAt: '', updatedAt: '' },
      { id: 'B', title: 'Node B', description: '', type: 'code', category: 'Dev', tags: [], importance: 0.5, status: 'HEALTHY', createdAt: '', updatedAt: '' },
      { id: 'C', title: 'Node C', description: '', type: 'code', category: 'Dev', tags: [], importance: 0.5, status: 'HEALTHY', createdAt: '', updatedAt: '' },
      { id: 'D', title: 'Node D', description: '', type: 'code', category: 'Dev', tags: [], importance: 0.5, status: 'HEALTHY', createdAt: '', updatedAt: '' },
      { id: 'E', title: 'Node E', description: '', type: 'code', category: 'Dev', tags: [], importance: 0.5, status: 'HEALTHY', createdAt: '', updatedAt: '' },
      { id: 'F', title: 'Node F', description: '', type: 'code', category: 'Dev', tags: [], importance: 0.5, status: 'HEALTHY', createdAt: '', updatedAt: '' },
      { id: 'G', title: 'Node G', description: '', type: 'code', category: 'Dev', tags: [], importance: 0.5, status: 'HEALTHY', createdAt: '', updatedAt: '' }
    ];

    const links: GraphLink[] = [
      { source: 'A', target: 'B', label: 'dependency' },
      { source: 'B', target: 'C', label: 'dependency' },
      { source: 'C', target: 'A', label: 'dependency' },
      { source: 'C', target: 'D', label: 'dependency' },
      { source: 'D', target: 'E', label: 'dependency' },
      { source: 'E', target: 'F', label: 'dependency' },
      { source: 'F', target: 'D', label: 'dependency' }
    ];

    // 2. Execute Analytics
    const results = GraphAnalytics.compute(nodes, links);

    // 3. Assertions & Verification
    // Orphan Node G should be identified
    expect(results.orphansCount).toBe(1);
    expect(results.nodeMetrics['G'].isOrphan).toBe(true);
    expect(results.nodeMetrics['A'].isOrphan).toBe(false);

    // Centrality
    expect(results.nodeMetrics['A'].degreeCentrality.total).toBe(2); // in: C, out: B
    expect(results.nodeMetrics['C'].degreeCentrality.total).toBe(3); // in: B, out: A, D

    // Weakly Connected Components (Component 1: {A..F}, Component 2: {G})
    expect(results.componentsCount).toBe(2);
    expect(results.nodeMetrics['A'].componentId).toBe(results.nodeMetrics['F'].componentId);
    expect(results.nodeMetrics['A'].componentId).not.toBe(results.nodeMetrics['G'].componentId);

    // Cycles (A, B, C, D, E, F should be flagged as inCycle)
    expect(results.nodeMetrics['A'].inCycle).toBe(true);
    expect(results.nodeMetrics['D'].inCycle).toBe(true);
    expect(results.nodeMetrics['G'].inCycle).toBe(false);

    // Bridge Nodes (C and D are articulation points / bridge nodes)
    expect(results.nodeMetrics['C'].isBridge).toBe(true);
    expect(results.nodeMetrics['D'].isBridge).toBe(true);
    expect(results.nodeMetrics['A'].isBridge).toBe(false);

    // 4. Shortest Path BFS Verification
    const pathAtoF = GraphAnalytics.findShortestPath(nodes, links, 'A', 'F');
    expect(pathAtoF).toEqual(['A', 'B', 'C', 'D', 'E', 'F']);

    const pathAtoG = GraphAnalytics.findShortestPath(nodes, links, 'A', 'G');
    expect(pathAtoG).toBeNull();
  });
});
