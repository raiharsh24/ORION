import React from 'react';
import { useKnowledgeStore } from '../store/useKnowledgeStore';

export const MiniMap: React.FC = () => {
  const { nodes } = useKnowledgeStore();

  // Compute absolute layout bounds dynamically
  let minX = -400;
  let maxX = 400;
  let minY = -400;
  let maxY = 400;

  if (nodes.length > 0) {
    nodes.forEach((node) => {
      const x = node.x ?? 0;
      const y = node.y ?? 0;
      if (x < minX) minX = x;
      if (x > maxX) maxX = x;
      if (y < minY) minY = y;
      if (y > maxY) maxY = y;
    });
  }

  const rangeX = maxX - minX || 1;
  const rangeY = maxY - minY || 1;

  const mapSize = 96; // Map viewport size

  return (
    <div className="absolute bottom-5 left-5 bg-black/50 border border-matte-border/30 backdrop-blur-md p-2.5 rounded-2xl flex flex-col items-center gap-1.5 select-none pointer-events-none z-20">
      <span className="font-mono text-[8px] text-zinc-500 uppercase tracking-widest">ATLAS MAP</span>
      <div 
        style={{ width: mapSize, height: mapSize }} 
        className="bg-black/30 border border-matte-border/20 rounded-xl relative overflow-hidden"
      >
        {/* Render a miniature dot representation of the database coordinates */}
        {nodes.map((node) => {
          // Skip drawing low importance nodes in minimap if list is large to maintain rendering frames
          if (nodes.length > 200 && node.importance < 0.6) return null;

          const nx = node.x ?? 0;
          const ny = node.y ?? 0;
          
          const left = ((nx - minX) / rangeX) * mapSize;
          const top = ((ny - minY) / rangeY) * mapSize;
          
          return (
            <div
              key={node.id}
              style={{
                position: 'absolute',
                left: Math.max(0, Math.min(mapSize - 3, left)),
                top: Math.max(0, Math.min(mapSize - 3, top)),
                width: '3px',
                height: '3px',
                borderRadius: '50%',
                backgroundColor: node.color || '#a1a1aa',
                boxShadow: node.importance > 0.8 ? `0 0 3px ${node.color}` : undefined
              }}
            />
          );
        })}
      </div>
    </div>
  );
};
export default MiniMap;
