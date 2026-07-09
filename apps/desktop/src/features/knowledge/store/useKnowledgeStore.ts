import { create } from 'zustand';
import type { GraphNode, GraphLink, LayoutMode, ProviderType } from '../types';
import { GraphEngine } from '../engine/GraphEngine';
import { GraphAnalytics } from '../engine/GraphAnalytics';
import type { NodeAnalytics } from '../engine/GraphAnalytics';
import { knowledgeApi } from '../../../services/api/knowledgeApi';
import { API_BASE_URL } from '../../../config/api';

export type HighlightMode =
  | 'normal'
  | 'dependencies'
  | 'imports'
  | 'inheritance'
  | 'documentation'
  | 'workflows'
  | 'memory'
  | 'analytics';

interface KnowledgeState {
  // Graph core datasets
  nodes: GraphNode[];
  links: GraphLink[];
  selectedNodeId: string | null;
  hoveredNodeId: string | null;
  
  // Search parameters
  searchQuery: string;
  searchResults: GraphNode[];
  activeProvider: ProviderType;
  
  // View bounds
  layoutMode: LayoutMode;
  width: number;
  height: number;

  // Custom Rendering Parameters
  nodeSize: number;
  linkStrength: number;
  physicsEnabled: boolean;
  rotationSpeed: number;
  labelVisibility: boolean;
  particleDensity: number;
  glowStrength: number;
  
  // Filter settings
  departmentFilter: string | null;
  showFolders: boolean;
  statusFilter: string | null;
  languageFilter: string | null;
  minImportance: number;
  nodeTypeFilter: string | null;
  tagFilter: string | null;
  
  // Highlight parameters
  highlightMode: HighlightMode;

  // Interactive controls
  bookmarks: string[];
  hiddenNodeIds: Set<string>;
  focusedSubtreeRootId: string | null;

  // Indexing & Diagnostics State
  indexingStatus: string;
  indexingProgress: number;
  indexingMessage: string;
  statsNodeCount: number;
  statsEdgeCount: number;
  activeSnapshotId: string | null;
  lastIndexDuration: number;
  recentErrors: any[];

  // Timeline / Snapshots
  snapshots: { snapshot_id: string; created_at: string; status: string }[];
  selectedSnapshotId: string | null;
  diffMode: boolean;
  
  // Diff tracking lists
  addedNodeIds: Set<string>;
  removedNodeIds: Set<string>;
  modifiedNodeIds: Set<string>;

  // Computed Graph Analytics cache
  analytics: {
    nodeMetrics: Record<string, NodeAnalytics>;
    cyclesCount: number;
    componentsCount: number;
    sccsCount: number;
    orphansCount: number;
  } | null;

  // Visualizer Setters
  setSelectedNodeId: (id: string | null) => void;
  setHoveredNodeId: (id: string | null) => void;
  setSearchQuery: (query: string) => void;
  setLayoutMode: (mode: LayoutMode) => void;
  setActiveProvider: (provider: ProviderType, snapshotId?: string) => Promise<void>;
  setDimensions: (width: number, height: number) => void;
  
  // Physics controls setters
  setNodeSize: (size: number) => void;
  setLinkStrength: (strength: number) => void;
  setPhysicsEnabled: (enabled: boolean) => void;
  setRotationSpeed: (speed: number) => void;
  setLabelVisibility: (visible: boolean) => void;
  setParticleDensity: (density: number) => void;
  setGlowStrength: (strength: number) => void;
  
  // Filter settings setters
  setDepartmentFilter: (dept: string | null) => void;
  setShowFolders: (show: boolean) => void;
  setFilters: (filters: {
    statusFilter?: string | null;
    languageFilter?: string | null;
    minImportance?: number;
    nodeTypeFilter?: string | null;
    tagFilter?: string | null;
  }) => void;
  resetFilters: () => void;

  // Highlight actions
  setHighlightMode: (mode: HighlightMode) => void;

  // Interaction actions
  addBookmark: (id: string) => void;
  removeBookmark: (id: string) => void;
  toggleHideNode: (id: string) => void;
  clearHiddenNodes: () => void;
  focusSubtree: (id: string | null) => void;
  collapseAllClusters: () => void;
  expandAllClusters: () => void;
  bakeSettings: () => void;

  // Indexing / Snapshots
  triggerIndex: () => Promise<void>;
  cancelIndex: () => Promise<void>;
  fetchHealth: () => Promise<void>;
  fetchSnapshots: () => Promise<void>;
  setSelectedSnapshotId: (snapshotId: string | null) => Promise<void>;
  setDiffMode: (diff: boolean) => Promise<void>;
  connectProgressStream: () => () => void;

  // Layout runner
  applyLayout: () => void;
  recomputeAnalytics: () => void;
  calculateSnapshotDiffs: (currentNodes: GraphNode[], baselineNodes: GraphNode[]) => void;
}

export const useKnowledgeStore = create<KnowledgeState>((set, get) => ({
  nodes: [],
  links: [],
  selectedNodeId: null,
  hoveredNodeId: null,
  searchQuery: '',
  searchResults: [],
  activeProvider: 'knowledge',
  layoutMode: 'rings',
  width: 800,
  height: 600,

  // Render defaults
  nodeSize: 1.0,
  linkStrength: 1.0,
  physicsEnabled: false,
  rotationSpeed: 0.0,
  labelVisibility: false,
  particleDensity: 1.0,
  glowStrength: 1.0,

  // Filter defaults
  departmentFilter: null,
  showFolders: true,
  statusFilter: null,
  languageFilter: null,
  minImportance: 0.0,
  nodeTypeFilter: null,
  tagFilter: null,

  // Highlight default
  highlightMode: 'normal',

  // Interactive controls defaults
  bookmarks: [],
  hiddenNodeIds: new Set<string>(),
  focusedSubtreeRootId: null,

  // Index defaults
  indexingStatus: 'IDLE',
  indexingProgress: 0,
  indexingMessage: '',
  statsNodeCount: 0,
  statsEdgeCount: 0,
  activeSnapshotId: null,
  lastIndexDuration: 0,
  recentErrors: [],

  // Timeline defaults
  snapshots: [],
  selectedSnapshotId: null,
  diffMode: false,

  addedNodeIds: new Set(),
  removedNodeIds: new Set(),
  modifiedNodeIds: new Set(),

  analytics: null,

  setSelectedNodeId: (id) => set({ selectedNodeId: id }),
  setHoveredNodeId: (id) => set({ hoveredNodeId: id }),

  setSearchQuery: (query) => {
    const { nodes } = get();
    const results = GraphEngine.search(nodes, query);
    set({ searchQuery: query, searchResults: results });
  },

  setLayoutMode: (mode) => {
    set({ layoutMode: mode, physicsEnabled: mode === 'force' });
    get().applyLayout();
  },

  setActiveProvider: async (providerType, snapshotId) => {
    const targetSnap = snapshotId || get().selectedSnapshotId || undefined;
    set({
      activeProvider: providerType,
      selectedNodeId: null,
      hoveredNodeId: null,
      searchQuery: '',
      searchResults: []
    });

    try {
      // Query specific snapshot if provided
      const data = await knowledgeApi.getGraph(providerType, targetSnap);
      
      // If diffMode is active, fetch previous snapshot to compare
      if (get().diffMode && get().snapshots.length > 1) {
        const snapIndex = get().snapshots.findIndex((s) => s.snapshot_id === (targetSnap || get().activeSnapshotId));
        if (snapIndex !== -1 && snapIndex + 1 < get().snapshots.length) {
          const prevSnapId = get().snapshots[snapIndex + 1].snapshot_id;
          try {
            const prevData = await knowledgeApi.getGraph(providerType, prevSnapId);
            get().calculateSnapshotDiffs(data.nodes, prevData.nodes);
          } catch (e) {
            console.error("Failed to fetch baseline snapshot for diffing:", e);
          }
        }
      } else {
        set({ addedNodeIds: new Set(), removedNodeIds: new Set(), modifiedNodeIds: new Set() });
      }

      set({ nodes: data.nodes, links: data.links });
      get().recomputeAnalytics();
      get().applyLayout();
    } catch (err) {
      console.error(`Failed to fetch graph data for provider '${providerType}':`, err);
      set({ nodes: [], links: [] });
    }
  },

  setDimensions: (width, height) => {
    set({ width, height });
    get().applyLayout();
  },

  // UI Control setters
  setNodeSize: (size) => set({ nodeSize: size }),
  setLinkStrength: (strength) => set({ linkStrength: strength }),
  setPhysicsEnabled: (enabled) => set({ physicsEnabled: enabled }),
  setRotationSpeed: (speed) => set({ rotationSpeed: speed }),
  setLabelVisibility: (visible) => set({ labelVisibility: visible }),
  setParticleDensity: (density) => set({ particleDensity: density }),
  setGlowStrength: (strength) => set({ glowStrength: strength }),

  setDepartmentFilter: (dept) => set({ departmentFilter: dept }),
  setShowFolders: (show) => set({ showFolders: show }),
  
  setFilters: (filters) => {
    set(filters);
    get().applyLayout();
  },

  resetFilters: () => {
    set({
      statusFilter: null,
      languageFilter: null,
      minImportance: 0.0,
      nodeTypeFilter: null,
      tagFilter: null,
      departmentFilter: null
    });
    get().applyLayout();
  },

  setHighlightMode: (mode) => set({ highlightMode: mode }),

  addBookmark: (id) => {
    set((state) => ({ bookmarks: [...state.bookmarks, id] }));
  },

  removeBookmark: (id) => {
    set((state) => ({ bookmarks: state.bookmarks.filter((b) => b !== id) }));
  },

  toggleHideNode: (id) => {
    const nextHidden = new Set(get().hiddenNodeIds);
    if (nextHidden.has(id)) {
      nextHidden.delete(id);
    } else {
      nextHidden.add(id);
    }
    set({ hiddenNodeIds: nextHidden, selectedNodeId: null });
  },

  clearHiddenNodes: () => set({ hiddenNodeIds: new Set() }),

  focusSubtree: (id) => set({ focusedSubtreeRootId: id, selectedNodeId: id }),

  triggerIndex: async () => {
    try {
      set({ indexingStatus: 'STARTING', indexingProgress: 0, indexingMessage: 'Triggering background scan...' });
      await knowledgeApi.triggerIndex();
    } catch (err) {
      console.error("Failed to trigger repository indexing:", err);
      set({ indexingStatus: 'FAILED', indexingMessage: 'Failed to trigger indexing.' });
    }
  },

  cancelIndex: async () => {
    try {
      await knowledgeApi.cancelIndex();
    } catch (err) {
      console.error("Failed to cancel active indexing:", err);
    }
  },

  fetchHealth: async () => {
    try {
      const stats = await knowledgeApi.getHealth();
      set({
        statsNodeCount: stats.node_count,
        statsEdgeCount: stats.edge_count,
        activeSnapshotId: stats.active_snapshot_id,
        lastIndexDuration: stats.last_indexing_duration,
        recentErrors: stats.recent_errors
      });
    } catch (err) {
      console.error("Failed to fetch health statistics:", err);
    }
  },

  fetchSnapshots: async () => {
    try {
      const snaps = await knowledgeApi.getSnapshots();
      set({ snapshots: snaps });
      if (snaps.length > 0 && !get().selectedSnapshotId) {
        set({ selectedSnapshotId: snaps[0].snapshot_id });
      }
    } catch (err) {
      console.error("Failed to fetch snapshots list:", err);
    }
  },

  setSelectedSnapshotId: async (snapshotId) => {
    set({ selectedSnapshotId: snapshotId });
    await get().setActiveProvider(get().activeProvider, snapshotId || undefined);
  },

  setDiffMode: async (diff) => {
    set({ diffMode: diff });
    await get().setActiveProvider(get().activeProvider);
  },

  connectProgressStream: () => {
    const eventSource = new EventSource(`${API_BASE_URL}/atlas/index/progress`);
    
    eventSource.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (payload.status === 'CONNECTED') {
          return;
        }
        
        set({
          indexingStatus: payload.status,
          indexingProgress: payload.progress,
          indexingMessage: payload.message
        });

        // Trigger updates on complete
        if (payload.status === 'COMPLETED') {
          get().setActiveProvider(get().activeProvider);
          get().fetchHealth();
          get().fetchSnapshots();
        }
      } catch (err) {
        console.error("Failed to parse SSE payload:", err);
      }
    };

    eventSource.onerror = () => {
      eventSource.close();
    };

    return () => {
      eventSource.close();
    };
  },

  recomputeAnalytics: () => {
    const { nodes, links } = get();
    if (nodes.length === 0) return;
    const stats = GraphAnalytics.compute(nodes, links);
    set({ analytics: stats });
  },

  calculateSnapshotDiffs: (currentNodes, baselineNodes) => {
    const currIds = new Set(currentNodes.map((n) => n.id));
    const baseIds = new Set(baselineNodes.map((n) => n.id));
    const baseMap = new Map(baselineNodes.map((n) => [n.id, n]));

    const added = new Set<string>();
    const removed = new Set<string>();
    const modified = new Set<string>();

    currentNodes.forEach((n) => {
      if (!baseIds.has(n.id)) {
        added.add(n.id);
      } else {
        const baseNode = baseMap.get(n.id);
        if (baseNode && (baseNode.metadata?.hash !== n.metadata?.hash || baseNode.metadata?.mtime !== n.metadata?.mtime)) {
          modified.add(n.id);
        }
      }
    });

    baselineNodes.forEach((n) => {
      if (!currIds.has(n.id)) {
        removed.add(n.id);
      }
    });

    set({ addedNodeIds: added, removedNodeIds: removed, modifiedNodeIds: modified });
  },

  applyLayout: () => {
    const { nodes, links, layoutMode, width, height, showFolders } = get();
    if (nodes.length === 0) return;

    const updatedNodes = nodes.map((node) => ({ ...node }));
    GraphEngine.applyLayout(updatedNodes, layoutMode, width, height, links, showFolders);

    set({ nodes: updatedNodes });
  },

  collapseAllClusters: () => {
    const { nodes, showFolders } = get();
    if (nodes.length === 0) return;

    const getFolderGroup = (node: GraphNode): string => {
      const path = node.metadata?.path || '';
      if (!path) return 'unknown';
      const parts = path.split('/');
      return parts.length <= 1 ? 'root' : parts.slice(0, -1).join('/');
    };

    const clusters: Record<string, GraphNode[]> = {};
    nodes.forEach((n) => {
      const g = showFolders ? getFolderGroup(n) : n.category;
      if (!clusters[g]) clusters[g] = [];
      clusters[g].push(n);
    });

    const toHide = new Set<string>();
    Object.keys(clusters).forEach((g) => {
      const list = clusters[g];
      if (list.length <= 1) return;

      let bestNode = list[0];
      list.forEach((n) => {
        if (n.id === 'friday' || n.importance > bestNode.importance) {
          bestNode = n;
        }
      });

      list.forEach((n) => {
        if (n.id !== bestNode.id && n.id !== 'friday') {
          toHide.add(n.id);
        }
      });
    });

    set({ hiddenNodeIds: toHide, selectedNodeId: null });
  },

  expandAllClusters: () => {
    set({ hiddenNodeIds: new Set() });
  },

  bakeSettings: () => {
    const { nodes } = get();
    const bakedNodes = nodes.map((node) => ({
      ...node,
      fx: node.x !== undefined ? node.x : node.fx,
      fy: node.y !== undefined ? node.y : node.fy
    }));
    set({ nodes: bakedNodes, physicsEnabled: false });
  },
}));

// Expose store for diagnostics (dev only)
if (typeof window !== 'undefined') {
  (window as any).__store = useKnowledgeStore;
}
