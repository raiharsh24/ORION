import type { GraphNode, GraphLink, GraphData, NodeStatus } from '../../types';

export class MockDataGenerator {
  private static cachedData: GraphData | null = null;

  public static generate(): GraphData {
    if (this.cachedData) {
      return this.cachedData;
    }

    const nodes: GraphNode[] = [];
    const links: GraphLink[] = [];

    // Department Cluster Color Mappings
    const categoryColors: Record<string, string> = {
      'Manifest': '#00f2fe',
      'Personal': '#ec4899', // Pink
      'Business': '#3b82f6', // Blue
      'Product': '#10b981', // Emerald
      'Development': '#8b5cf6', // Purple
      'Research': '#eab308', // Yellow
      'Community': '#f97316', // Orange
      'Content': '#06b6d4', // Cyan
      'Memory': '#14b8a6', // Teal
      'Documents': '#64748b' // Slate
    };

    // Helper to generate a date offset in ISO string format
    const generateDate = (daysAgo: number): string => {
      const date = new Date();
      date.setDate(date.getDate() - daysAgo);
      return date.toISOString();
    };

    // 1. ROOT NODE (FRIDAY.md)
    const rootNode: GraphNode = {
      id: 'friday',
      title: 'FRIDAY.md',
      description: 'The master manifest and workspace configuration representing the core of FRIDAY OS.',
      type: 'manifest',
      category: 'Manifest',
      tags: ['workspace', 'system', 'root'],
      metadata: { version: '0.4.0', core_build: 'release-rc1' },
      createdAt: generateDate(60),
      updatedAt: generateDate(0),
      importance: 1.0,
      status: 'HEALTHY',
      color: categoryColors['Manifest'],
      icon: 'Sparkles',
      fx: 0,
      fy: 0
    };
    nodes.push(rootNode);

    // 2. CORE AGENTS (6 Nodes)
    const agentsList = [
      { id: 'agent_planner', title: 'Planner Agent', desc: 'Synthesizes tasks and plans execution pathways.', cat: 'Development', status: 'HEALTHY' as NodeStatus },
      { id: 'agent_research', title: 'Research Agent', desc: 'Extracts references, details, and summaries from web searches.', cat: 'Research', status: 'HEALTHY' as NodeStatus },
      { id: 'agent_coding', title: 'Coding Agent', desc: 'Drafts, compiles, and audits codebase changes.', cat: 'Development', status: 'HEALTHY' as NodeStatus },
      { id: 'agent_memory', title: 'Memory Agent', desc: 'Handles consolidations and stores relevant contextual associations.', cat: 'Memory', status: 'WARNING' as NodeStatus },
      { id: 'agent_automation', title: 'Automation Agent', desc: 'Triggers keyboard/mouse sequences and coordinates workflow runtime steps.', cat: 'Product', status: 'HEALTHY' as NodeStatus },
      { id: 'agent_ui', title: 'UI Agent', desc: 'Maintains Zustand client caches, routes, and canvas visual frames.', cat: 'Product', status: 'HEALTHY' as NodeStatus }
    ];

    agentsList.forEach((agent, i) => {
      const angle = (2 * Math.PI * i) / agentsList.length;
      const radius = 100;
      nodes.push({
        id: agent.id,
        title: agent.title,
        description: agent.desc,
        type: 'agent',
        category: agent.cat,
        tags: ['agent', 'core', agent.id.split('_')[1]],
        metadata: { status: agent.status, priority: 'critical' },
        createdAt: generateDate(30),
        updatedAt: generateDate(1),
        importance: 0.9,
        status: agent.status,
        color: categoryColors[agent.cat],
        icon: 'Cpu',
        fx: radius * Math.cos(angle),
        fy: radius * Math.sin(angle)
      });

      links.push({
        source: 'friday',
        target: agent.id,
        label: 'Orchestrates',
        value: 4.5,
        color: 'rgba(0, 242, 254, 0.45)'
      });
    });

    // 3. APPLICATIONS (15 Nodes)
    const apps = [
      { id: 'app_chat', title: 'Assistant Portal', desc: 'User assistant interface for prompts and queries.', cat: 'Personal' },
      { id: 'app_dashboard', title: 'Telemetry Center', desc: 'Interactive CPU, memory, and status tracking dashboards.', cat: 'Product' },
      { id: 'app_missions', title: 'Mission Panel', desc: 'Task orchestrator tracking execution queue stages.', cat: 'Product' },
      { id: 'app_projects', title: 'Repository Manager', desc: 'Workspace browser and semantic splitting parameters.', cat: 'Development' },
      { id: 'app_terminal', title: 'Futuristic Shell', desc: 'Integrated terminal wrapper execution environment.', cat: 'Development' },
      { id: 'app_settings', title: 'System Settings', desc: 'Authentication, API token keys, and voice providers controls.', cat: 'Personal' },
      { id: 'app_knowledge', title: 'Atlas Visualizer', desc: 'Interactive knowledge map canvas interface.', cat: 'Manifest' }
    ];

    apps.forEach((app, i) => {
      const angle = (2 * Math.PI * i) / apps.length + 0.3;
      const radius = 220;
      nodes.push({
        id: app.id,
        title: app.title,
        description: app.desc,
        type: 'application',
        category: app.cat,
        tags: ['application', 'ui', app.id.split('_')[1]],
        metadata: { desktop_integration: true },
        createdAt: generateDate(45),
        updatedAt: generateDate(0),
        importance: 0.8,
        status: 'HEALTHY',
        color: categoryColors[app.cat] || '#00f2fe',
        icon: 'Grid',
        fx: radius * Math.cos(angle),
        fy: radius * Math.sin(angle)
      });

      links.push({
        source: 'friday',
        target: app.id,
        label: 'Launches',
        value: 3.5
      });
    });

    // 4. SKILLS & ROUTINES (100 Nodes)
    for (let i = 0; i < 40; i++) {
      const skillId = `skill_${i}`;
      const parentAgent = agentsList[i % agentsList.length].id;
      const cat = i % 2 === 0 ? 'Development' : 'Product';
      const angle = (i * 0.15);
      const radius = 130 + (i % 3) * 20;

      nodes.push({
        id: skillId,
        title: `Skill: ${i % 3 === 0 ? 'File API ' : i % 3 === 1 ? 'Terminal Command ' : 'Voice Synthesize '}${i}`,
        description: `Reusable software execution skill registering capability mappings for ${parentAgent}.`,
        type: 'skill',
        category: cat,
        tags: ['skill', 'capability', `exec_${i}`],
        metadata: { permissions: 'user_approval_required' },
        createdAt: generateDate(20),
        updatedAt: generateDate(5),
        importance: 0.5,
        status: 'HEALTHY',
        color: categoryColors[cat],
        icon: 'Wrench',
        fx: radius * Math.cos(angle),
        fy: radius * Math.sin(angle)
      });

      links.push({
        source: parentAgent,
        target: skillId,
        label: 'Implements',
        value: 2.0
      });
    }

    // Routines (60 Nodes)
    for (let i = 0; i < 60; i++) {
      const routineId = `routine_${i}`;
      const cat = i % 3 === 0 ? 'Personal' : i % 3 === 1 ? 'Business' : 'Community';
      const angle = (i * 0.1);
      const radius = 320 + (i % 2) * 15;

      nodes.push({
        id: routineId,
        title: `Routine: Morning Brief #${i}`,
        description: `Automated scheduled cron routines running checks and compiling briefings.`,
        type: 'routine',
        category: cat,
        tags: ['routine', 'cron', 'schedule'],
        metadata: { frequency: 'daily', cron: '0 8 * * *' },
        createdAt: generateDate(25),
        updatedAt: generateDate(2),
        importance: 0.45,
        status: 'HEALTHY',
        color: categoryColors[cat],
        icon: 'Clock',
        fx: radius * Math.cos(angle),
        fy: radius * Math.sin(angle)
      });

      links.push({
        source: 'friday',
        target: routineId,
        label: 'Schedules',
        value: 1.8
      });
    }

    // Helper for bulk nodes distribution
    const generateClusterNodes = (
      prefix: string,
      count: number,
      type: string,
      category: string,
      importance: number,
      baseRadius: number,
      angleStart: number,
      angleEnd: number,
      icon: string
    ) => {
      const statusOptions: NodeStatus[] = ['HEALTHY', 'HEALTHY', 'HEALTHY', 'WARNING', 'HEALTHY'];
      for (let i = 0; i < count; i++) {
        const id = `${prefix}_${i}`;
        const ratio = i / count;
        const angle = angleStart + ratio * (angleEnd - angleStart) + (Math.random() - 0.5) * 0.08;
        const radius = baseRadius + (Math.random() - 0.5) * 120;
        const status = statusOptions[Math.floor(Math.random() * statusOptions.length)];
        
        nodes.push({
          id,
          title: `${type.toUpperCase()}: ${prefix.replace('_', ' ')} index #${i}`,
          description: `Generated ${type} node detailing system elements inside ATLAS database, representing active properties.`,
          type,
          category,
          tags: [type, category.toLowerCase(), `tag_${i % 10}`],
          metadata: { size_bytes: Math.floor(Math.random() * 5000) + 120, index: i },
          createdAt: generateDate(Math.floor(Math.random() * 30) + 1),
          updatedAt: generateDate(Math.floor(Math.random() * 5)),
          importance,
          status,
          color: categoryColors[category],
          icon,
          // Starting coordinates assigned logically
          x: radius * Math.cos(angle),
          y: radius * Math.sin(angle)
        });

        // Relate back to parent/applications
        if (i % 20 === 0) {
          const targetApp = apps[i % apps.length].id;
          links.push({
            source: id,
            target: targetApp,
            label: 'Belongs to',
            value: 1.0
          });
        }
      }
    };

    // 5. MEMORY CLUSTER (3,000 Nodes)
    // Sector: Angle range (1.2 to 2.4)
    generateClusterNodes('mem_fact', 1000, 'memory', 'Memory', 0.25, 450, 1.2, 1.6, 'Brain');
    generateClusterNodes('mem_conv', 1000, 'memory', 'Memory', 0.2, 550, 1.6, 2.0, 'MessageCircle');
    generateClusterNodes('mem_pref', 1000, 'memory', 'Memory', 0.3, 620, 2.0, 2.4, 'Bookmark');

    // Link a fraction of memory nodes to memory agent
    for (let i = 0; i < 3000; i += 80) {
      links.push({
        source: 'agent_memory',
        target: `mem_fact_${i}`,
        label: 'Consolidates',
        value: 1.2
      });
    }

    // 6. CODE GRAPH (3,000 Nodes)
    // Sector: Angle range (2.5 to 3.8)
    generateClusterNodes('code_fe', 1000, 'code', 'Development', 0.35, 480, 2.5, 2.9, 'FileCode');
    generateClusterNodes('code_api', 1000, 'code', 'Development', 0.3, 580, 2.9, 3.4, 'Terminal');
    generateClusterNodes('code_shared', 1000, 'code', 'Development', 0.4, 650, 3.4, 3.8, 'Hash');

    // Link code nodes to code agent
    for (let i = 0; i < 3000; i += 75) {
      links.push({
        source: 'agent_coding',
        target: `code_fe_${i}`,
        label: 'Audits',
        value: 1.3
      });
    }

    // 7. DOCUMENTS & RESEARCH (2,000 Nodes)
    // Sector: Angle range (3.9 to 5.2)
    generateClusterNodes('doc_markdown', 1000, 'document', 'Documents', 0.35, 520, 3.9, 4.5, 'FileText');
    generateClusterNodes('research_reference', 1000, 'research', 'Research', 0.3, 600, 4.5, 5.2, 'BookOpen');

    // Link documents and research nodes
    for (let i = 0; i < 1000; i += 50) {
      links.push({
        source: 'agent_research',
        target: `research_reference_${i}`,
        label: 'Scrapes',
        value: 1.4
      });
    }

    // 8. WORKFLOWS STEPS (800 Nodes)
    // Sector: Angle range (5.3 to 6.2)
    generateClusterNodes('wf_step', 800, 'workflow', 'Product', 0.3, 500, 5.3, 6.2, 'Layers');

    // Link workflow nodes to automation agent
    for (let i = 0; i < 800; i += 40) {
      links.push({
        source: 'agent_automation',
        target: `wf_step_${i}`,
        label: 'Runs',
        value: 1.5
      });
    }

    // 9. Extra Inter-node Relationships (Realistic dependency linking)
    // Connect Memories to Code, Documents to Workflows, etc.
    for (let i = 0; i < 150; i++) {
      const memId = `mem_fact_${i * 5}`;
      const codeId = `code_fe_${i * 6}`;
      const docId = `doc_markdown_${i * 5}`;
      const wfId = `wf_step_${i * 4}`;

      links.push({
        source: memId,
        target: codeId,
        label: 'Associates code context',
        value: 0.8
      });

      links.push({
        source: docId,
        target: wfId,
        label: 'Explains process',
        value: 0.9
      });
    }

    this.cachedData = { nodes, links };
    return this.cachedData;
  }
}
