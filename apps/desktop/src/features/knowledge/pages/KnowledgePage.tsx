import React, { useEffect, useState } from 'react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../../../components/ui/Card';
import { Button } from '../../../components/ui/Button';
import { Input } from '../../../components/ui/Input';
import { useSystemStore } from '../../../store/useSystemStore';
import { 
  FolderGit, 
  Search, 
  RefreshCw, 
  GitBranch, 
  Info,
  Database,
  Network
} from 'lucide-react';

// Knowledge Graph Component
import { KnowledgeGraph } from './KnowledgeGraph';

export const KnowledgePage: React.FC = () => {
  const {
    workspaceProjects,
    indexingInProgress,
    searchResults,
    fetchWorkspaceProjects,
    triggerIndexing,
    performKnowledgeSearch
  } = useSystemStore();

  const [activeTab, setActiveTab] = useState<'graph' | 'indexing'>('graph');
  const [searchQuery, setSearchQuery] = useState('');
  const [customPath, setCustomPath] = useState('');
  const [customProjName, setCustomProjName] = useState('');

  useEffect(() => {
    fetchWorkspaceProjects();
  }, []);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;
    performKnowledgeSearch(searchQuery);
  };

  const handleIndexDefault = () => {
    triggerIndexing();
  };

  const handleIndexCustom = (e: React.FormEvent) => {
    e.preventDefault();
    if (!customPath.trim()) return;
    triggerIndexing(customPath, customProjName.trim() || undefined);
    setCustomPath('');
    setCustomProjName('');
  };

  return (
    <div className="space-y-6 select-none pb-8">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-4">
        <div>
          <h1 className="text-3xl font-extrabold text-zinc-100 tracking-tight flex items-center gap-3">
            <Database className="w-8 h-8 text-cyan-glow" />
            Workspace Knowledge Engine
          </h1>
          <p className="font-mono text-xs text-zinc-500 tracking-wider mt-1 uppercase">
            Graph visualization, workspace indexing, and local vector retrieval
          </p>
        </div>

        {/* Tab Selector */}
        <div className="flex bg-black/60 border border-matte-border p-1 rounded-xl">
          <button
            onClick={() => setActiveTab('graph')}
            className={`flex items-center gap-2 px-4 py-2 font-mono text-xs tracking-wider rounded-lg transition-all cursor-pointer
              ${activeTab === 'graph'
                ? 'bg-cyan-dim/15 text-cyan-glow border-b-2 border-cyan-glow font-bold'
                : 'text-zinc-500 hover:text-zinc-300'
              }
            `}
          >
            <Network className="w-4 h-4" />
            GRAPH VISUALIZER
          </button>
          <button
            onClick={() => setActiveTab('indexing')}
            className={`flex items-center gap-2 px-4 py-2 font-mono text-xs tracking-wider rounded-lg transition-all cursor-pointer
              ${activeTab === 'indexing'
                ? 'bg-cyan-dim/15 text-cyan-glow border-b-2 border-cyan-glow font-bold'
                : 'text-zinc-500 hover:text-zinc-300'
              }
            `}
          >
            <RefreshCw className="w-4 h-4" />
            INDEXING & SEARCH
          </button>
        </div>
      </div>

      {/* Tab Content Rendering */}
      {activeTab === 'graph' ? (
        <KnowledgeGraph />
      ) : (
        <div className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Left Side: Projects Discovered */}
            <div className="lg:col-span-2 space-y-6">
              <Card variant="glow">
                <CardHeader className="flex flex-row items-center justify-between pb-2">
                  <div>
                    <CardTitle>Workspace Repositories</CardTitle>
                    <CardDescription>Local files & projects scanned in target workspace directory</CardDescription>
                  </div>
                  <span className="font-mono text-[9px] bg-cyan-dim/20 text-cyan-glow border border-cyan-border/25 px-2 py-0.5 rounded font-bold">
                    {workspaceProjects.length} TRACKED
                  </span>
                </CardHeader>
                <CardContent className="space-y-4">
                  {workspaceProjects.length === 0 ? (
                    <div className="text-center py-12 border border-dashed border-matte-border/50 rounded-xl font-mono text-xs text-zinc-600">
                      NO ACTIVE PROJECTS DETECTED. CLICK RE-SCAN TO DISCOVER.
                    </div>
                  ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {workspaceProjects.map((proj, idx) => (
                        <div 
                          key={idx}
                          className="p-4 bg-black/40 border border-matte-border hover:border-cyan-border/25 rounded-xl flex flex-col justify-between gap-3 group transition-all"
                        >
                          <div>
                            <div className="flex items-start justify-between gap-2">
                              <span className="font-bold text-zinc-200 group-hover:text-cyan-glow text-sm truncate font-mono">
                                {proj.name}
                              </span>
                              {proj.is_git ? (
                                <span className="flex items-center gap-1 text-[9px] font-mono text-zinc-500 uppercase tracking-widest bg-zinc-900 border border-zinc-800 px-1.5 py-0.5 rounded-md">
                                  <FolderGit className="w-3 h-3 text-cyan-glow" /> GIT
                                </span>
                              ) : (
                                <span className="text-[9px] font-mono text-zinc-600 uppercase bg-zinc-950 px-1.5 py-0.5 rounded-md">
                                  DIR
                                </span>
                              )}
                            </div>
                            <p className="font-mono text-[10px] text-zinc-500 truncate mt-1.5" title={proj.path}>
                              {proj.path}
                            </p>
                          </div>

                          <div className="flex flex-wrap gap-2 pt-2 border-t border-matte-border/30">
                            {proj.branch && (
                              <span className="flex items-center gap-1 font-mono text-[9px] text-zinc-400 bg-zinc-900 border border-zinc-800 px-2 py-0.5 rounded-full">
                                <GitBranch className="w-2.5 h-2.5 text-cyan-glow" /> {proj.branch}
                              </span>
                            )}
                            <span className="font-mono text-[9px] text-zinc-400 bg-zinc-900 border border-zinc-800 px-2 py-0.5 rounded-full">
                              {proj.files_count} files
                            </span>
                            {proj.languages.map((lang, lIdx) => (
                              <span key={lIdx} className="font-mono text-[9px] text-cyan-glow/80 bg-cyan-dim/10 border border-cyan-border/10 px-2 py-0.5 rounded-full">
                                {lang}
                              </span>
                            ))}
                          </div>

                          <Button 
                            onClick={() => triggerIndexing(proj.path, proj.name)}
                            className="w-full h-8 font-mono text-[10px] tracking-wider mt-2 bg-zinc-900 hover:bg-cyan-glow hover:text-black border border-matte-border hover:border-transparent"
                            disabled={indexingInProgress}
                          >
                            {indexingInProgress ? 'INDEXING...' : 'RE-INDEX PROJECT'}
                          </Button>
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Custom Path Indexer Card */}
              <Card variant="default">
                <CardHeader>
                  <CardTitle>Index Custom Directory</CardTitle>
                  <CardDescription>Parse and embed custom repository directories manually</CardDescription>
                </CardHeader>
                <CardContent>
                  <form onSubmit={handleIndexCustom} className="space-y-4">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div className="space-y-1.5">
                        <label className="font-mono text-[10px] text-zinc-500 uppercase tracking-wider">Absolute Folder Path</label>
                        <Input 
                          value={customPath}
                          onChange={(e) => setCustomPath(e.target.value)}
                          placeholder="/home/warlock/ORION/packages/utils"
                          required
                        />
                      </div>
                      <div className="space-y-1.5">
                        <label className="font-mono text-[10px] text-zinc-500 uppercase tracking-wider">Project Display Name (Optional)</label>
                        <Input 
                          value={customProjName}
                          onChange={(e) => setCustomProjName(e.target.value)}
                          placeholder="utility-library"
                        />
                      </div>
                    </div>
                    <Button 
                      type="submit" 
                      disabled={indexingInProgress || !customPath.trim()} 
                      className="font-mono text-xs w-full h-10"
                    >
                      {indexingInProgress ? 'RUNNING PARSER & PIPELINES...' : 'INDEX CHUNKS INTO VECTOR DB'}
                    </Button>
                  </form>
                </CardContent>
              </Card>
            </div>

            {/* Right Side: Index Status / Quick Actions */}
            <div className="space-y-6">
              <Card variant="default">
                <CardHeader>
                  <CardTitle>Indexing Status</CardTitle>
                  <CardDescription>Live vector database tracking</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex items-center justify-between p-3 bg-black/40 border border-matte-border rounded-xl font-mono text-xs">
                    <span className="text-zinc-400">Database Engine</span>
                    <span className="text-cyan-glow font-bold uppercase">ChromaDB / Fallback</span>
                  </div>
                  <div className="flex items-center justify-between p-3 bg-black/40 border border-matte-border rounded-xl font-mono text-xs">
                    <span className="text-zinc-400">Status</span>
                    <span className="flex items-center gap-1.5 text-zinc-300">
                      <span className={`h-2 w-2 rounded-full ${indexingInProgress ? 'bg-amber-400 animate-pulse' : 'bg-emerald-500'}`} />
                      {indexingInProgress ? 'INDEXING...' : 'NOMINAL // IDLE'}
                    </span>
                  </div>
                  <Button 
                    onClick={handleIndexDefault} 
                    disabled={indexingInProgress} 
                    className="w-full font-mono text-xs h-10 bg-cyan-glow hover:bg-cyan-glow/85 text-black border-none"
                  >
                    INDEX DEFAULT WORKSPACE
                  </Button>
                </CardContent>
              </Card>

              <Card variant="default">
                <CardHeader>
                  <div className="flex items-center gap-2">
                    <Info className="w-4 h-4 text-cyan-glow" />
                    <CardTitle className="text-sm">Semantic Splitting Details</CardTitle>
                  </div>
                </CardHeader>
                <CardContent className="font-mono text-[10px] text-zinc-500 space-y-2.5 leading-relaxed uppercase">
                  <p>✔ File chunk boundaries: 1000 characters.</p>
                  <p>✔ Overlap spacing threshold: 150 characters.</p>
                  <p>✔ Supported formats: md, txt, py, js, ts, tsx, jsx, json, pdf.</p>
                  <p>✔ Auto-prunes node_modules and dot folders.</p>
                </CardContent>
              </Card>
            </div>
          </div>

          {/* Bottom: Semantic Document Retrieval sandbox */}
          <Card variant="glow" className="mt-8">
            <CardHeader>
              <CardTitle>Semantic Code & Documentation Search Sandbox</CardTitle>
              <CardDescription>Perform real-time queries against the local vector database embeddings</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <form onSubmit={handleSearch} className="flex gap-3">
                <Input 
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Type semantic query (e.g. 'how does orchestrator handle tool confirmations?')..."
                  className="flex-1"
                  icon={<Search className="w-4 h-4 text-zinc-500" />}
                />
                <Button type="submit" className="font-mono text-xs px-6" disabled={!searchQuery.trim()}>
                  SEARCH DB
                </Button>
              </form>

              {/* Results grid */}
              <div className="space-y-4">
                {searchResults.length === 0 ? (
                  <div className="text-center py-12 font-mono text-xs text-zinc-600 border border-matte-border/30 rounded-xl">
                    ENTER A SEMANTIC QUERY TO PREVIEW MATCHING DOCUMENT CHUNKS.
                  </div>
                ) : (
                  searchResults.map((result, idx) => (
                    <div 
                      key={result.id}
                      className="bg-black/60 border border-matte-border rounded-xl p-5 space-y-3 font-mono text-xs select-text"
                    >
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-2 border-b border-matte-border/20 text-[10px]">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="text-zinc-500 font-bold">MATCH [{idx+1}]</span>
                          <span className="text-cyan-glow font-bold bg-cyan-dim/15 px-2 py-0.5 rounded border border-cyan-border/10">
                            {result.metadata.project_name}
                          </span>
                          <span className="text-zinc-400 truncate max-w-md" title={result.metadata.file_path}>
                            {result.metadata.file_path.split('/').pop()} ({result.metadata.file_type.toUpperCase()})
                          </span>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="text-zinc-500">SIMILARITY SCORE:</span>
                          <span className="text-emerald-400 font-extrabold bg-emerald-950/20 px-2 py-0.5 rounded border border-emerald-500/10">
                            {(result.score * 100).toFixed(1)}%
                          </span>
                        </div>
                      </div>
                      <pre className="bg-black p-4 rounded-lg overflow-x-auto text-[11px] leading-relaxed text-zinc-300 border border-matte-border/40 max-h-[220px] scrollbar-thin whitespace-pre-wrap select-text">
                        {result.document}
                      </pre>
                      <div className="text-[9px] text-zinc-500 flex justify-between gap-4 select-none">
                        <span>Chunk ID: {result.id}</span>
                        <span>Segment index: {result.metadata.chunk_index}</span>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
};
export default KnowledgePage;
