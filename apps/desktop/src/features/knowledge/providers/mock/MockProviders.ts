import type { GraphProvider } from '../GraphProvider';
import type { GraphData, GraphNode, GraphLink, ProviderType } from '../../types';
import { MockDataGenerator } from './MockDataGenerator';

// Helper to filter links so that links only connect nodes present in the sub-graph
const getConnectedLinks = (nodesList: GraphNode[], allLinks: GraphLink[]): GraphLink[] => {
  const nodeIds = new Set(nodesList.map((node) => node.id));
  return allLinks.filter((link) => {
    const sourceId = typeof link.source === 'string' ? link.source : (link.source as any).id;
    const targetId = typeof link.target === 'string' ? link.target : (link.target as any).id;
    return nodeIds.has(sourceId) && nodeIds.has(targetId);
  });
};

class BaseMockProvider implements GraphProvider {
  public type: ProviderType;
  public name: string;
  private filterFn: (node: GraphNode) => boolean;

  constructor(
    type: ProviderType,
    name: string,
    filterFn: (node: GraphNode) => boolean
  ) {
    this.type = type;
    this.name = name;
    this.filterFn = filterFn;
  }

  async fetchGraphData(): Promise<GraphData> {
    const allData = MockDataGenerator.generate();
    
    // Always include the FRIDAY manifest as the central anchor root
    const filteredNodes = allData.nodes.filter(
      (node) => node.id === 'friday' || this.filterFn(node)
    );
    
    const filteredLinks = getConnectedLinks(filteredNodes, allData.links);

    return {
      nodes: filteredNodes,
      links: filteredLinks
    };
  }
}

export const KnowledgeProvider = new BaseMockProvider(
  'knowledge',
  'Workspace Map (Atlas)',
  (node) => node.type === 'agent' || node.type === 'application' || node.type === 'skill' || node.type === 'routine'
);

export const MemoryProvider = new BaseMockProvider(
  'memory',
  'Cognitive Memory',
  (node) => node.type === 'memory' || node.id === 'agent_memory'
);

export const CodeProvider = new BaseMockProvider(
  'code',
  'Codebase Architecture',
  (node) => node.type === 'code' || node.id === 'agent_coding'
);

export const WorkflowProvider = new BaseMockProvider(
  'workflow',
  'Workflow Runtime',
  (node) => node.type === 'workflow' || node.id === 'agent_automation'
);

export const AgentProvider = new BaseMockProvider(
  'agent',
  'Collaborative Agents',
  (node) => node.type === 'agent' || node.type === 'skill'
);

export const DocumentProvider = new BaseMockProvider(
  'document',
  'Document Vault',
  (node) => node.type === 'document' || node.type === 'manifest'
);

export const ResearchProvider = new BaseMockProvider(
  'research',
  'Research Archives',
  (node) => node.type === 'research' || node.id === 'agent_research'
);

export const TimelineProvider = new BaseMockProvider(
  'timeline',
  'Chronological Events',
  (node) => node.type === 'routine' || node.type === 'manifest'
);

export const mockProviders: Record<ProviderType, GraphProvider> = {
  knowledge: KnowledgeProvider,
  memory: MemoryProvider,
  code: CodeProvider,
  workflow: WorkflowProvider,
  agent: AgentProvider,
  document: DocumentProvider,
  research: ResearchProvider,
  timeline: TimelineProvider
};
