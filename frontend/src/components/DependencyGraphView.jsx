import React, { useEffect, useState, useCallback, useMemo } from 'react';
import {
  ReactFlow,
  MiniMap,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  Handle,
  Position,
  MarkerType,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import {
  Network,
  FileCode2,
  Package,
  Layers,
  Sparkles,
  ArrowRightLeft,
  Maximize2,
  Compass,
} from 'lucide-react';
import dagre from 'dagre';

const nodeWidth = 220;
const nodeHeight = 88;

const getLayoutedElements = (nodes, edges, direction = 'LR') => {
  const dagreGraph = new dagre.graphlib.Graph();
  dagreGraph.setDefaultEdgeLabel(() => ({}));
  dagreGraph.setGraph({
    rankdir: direction,
    ranksep: direction === 'LR' ? 100 : 70,
    nodesep: direction === 'LR' ? 40 : 60,
  });

  const nodeSet = new Set(nodes.map((n) => n.id));

  nodes.forEach((node) => {
    dagreGraph.setNode(node.id, { width: nodeWidth, height: nodeHeight });
  });

  const validEdges = [];
  edges.forEach((edge) => {
    if (nodeSet.has(edge.source) && nodeSet.has(edge.target)) {
      dagreGraph.setEdge(edge.source, edge.target);
      validEdges.push({
        ...edge,
        type: 'smoothstep',
        animated: true,
        style: { stroke: '#22D3EE', strokeWidth: 2.5, strokeDasharray: '6, 4' },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: '#22D3EE',
          width: 22,
          height: 22,
        },
      });
    }
  });

  dagre.layout(dagreGraph);

  const isHorizontal = direction === 'LR';

  const newNodes = nodes.map((node, idx) => {
    const nodeWithPosition = dagreGraph.node(node.id);
    return {
      ...node,
      targetPosition: isHorizontal ? Position.Left : Position.Top,
      sourcePosition: isHorizontal ? Position.Right : Position.Bottom,
      position: {
        x: nodeWithPosition ? nodeWithPosition.x - nodeWidth / 2 : (idx % 5) * 240,
        y: nodeWithPosition ? nodeWithPosition.y - nodeHeight / 2 : Math.floor(idx / 5) * 110,
      },
    };
  });

  return { nodes: newNodes, edges: validEdges };
};

// ── Custom Node Component ──────────────────────────────────────────────────
const FileNode = ({ data, isConnectable }) => {
  const isExternal = data.language === 'external';
  const fileName = data.label?.split(/[\/\\]/).pop() || data.label;
  const dirPath = data.label?.includes('/') || data.label?.includes('\\')
    ? data.label.substring(0, Math.max(data.label.lastIndexOf('/'), data.label.lastIndexOf('\\')))
    : '';

  return (
    <div
      className={`px-3.5 py-2.5 shadow-2xl rounded-xl border backdrop-blur-md transition-all duration-200 min-w-[190px] max-w-[230px] select-none relative ${
        isExternal
          ? 'bg-[#150d2a]/95 border-purple-500/50 hover:border-purple-400 shadow-purple-950/40'
          : 'bg-[#0B1120]/95 border-indigo-500/40 hover:border-cyan-400 shadow-indigo-950/40'
      }`}
    >
      <Handle
        type="target"
        position={data.targetPosition || Position.Left}
        isConnectable={isConnectable}
        className="w-2.5 h-2.5 !bg-cyan-400 !border-2 !border-gray-950"
      />

      <div className="flex items-center gap-2 mb-1">
        {isExternal ? (
          <Package className="w-4 h-4 text-purple-400 flex-shrink-0" />
        ) : (
          <FileCode2 className="w-4 h-4 text-cyan-400 flex-shrink-0" />
        )}
        <div className="text-xs font-bold text-gray-100 truncate font-mono" title={data.label}>
          {fileName}
        </div>
      </div>

      {dirPath ? (
        <div className="text-[10px] text-gray-400 truncate font-mono opacity-60 mb-2" title={data.label}>
          {dirPath}
        </div>
      ) : (
        <div className="text-[10px] text-gray-500 font-mono opacity-50 mb-2">root</div>
      )}

      <div className="flex items-center justify-between pt-1.5 border-t border-gray-800/80">
        <span
          className={`text-[9px] uppercase font-bold px-1.5 py-0.5 rounded tracking-wider ${
            isExternal
              ? 'bg-purple-950/80 text-purple-300 border border-purple-800/60'
              : 'bg-indigo-950/80 text-cyan-300 border border-indigo-800/60'
          }`}
        >
          {data.language || 'code'}
        </span>
        {!isExternal && data.loc > 0 && (
          <span className="text-[10px] font-mono text-emerald-400 font-medium">
            {data.loc} LOC
          </span>
        )}
      </div>

      <Handle
        type="source"
        position={data.sourcePosition || Position.Right}
        isConnectable={isConnectable}
        className="w-2.5 h-2.5 !bg-indigo-400 !border-2 !border-gray-950"
      />
    </div>
  );
};

export default function DependencyGraphView({ graphData }) {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [direction, setDirection] = useState('LR');

  const nodeTypes = useMemo(() => ({ fileNode: FileNode }), []);

  const applyLayout = useCallback(
    (dir) => {
      if (graphData && graphData.nodes && graphData.nodes.length > 0) {
        const { nodes: layoutedNodes, edges: layoutedEdges } = getLayoutedElements(
          graphData.nodes,
          graphData.edges || [],
          dir
        );
        setNodes([...layoutedNodes]);
        setEdges([...layoutedEdges]);
      } else {
        setNodes([]);
        setEdges([]);
      }
    },
    [graphData, setNodes, setEdges]
  );

  useEffect(() => {
    applyLayout(direction);
  }, [graphData, direction, applyLayout]);

  const toggleDirection = () => {
    setDirection((prev) => (prev === 'LR' ? 'TB' : 'LR'));
  };

  const hasNodes = nodes.length > 0;

  return (
    <div className="flex flex-col h-full rounded-2xl glass-panel border border-gray-800 bg-[#0A0E1A] overflow-hidden shadow-2xl relative">
      {/* Header Bar */}
      <div className="flex items-center justify-between px-5 py-3 bg-gray-900/90 border-b border-gray-800/90 z-10 backdrop-blur-md">
        <div className="flex items-center gap-2.5">
          <Network className="w-4 h-4 text-cyan-400 animate-pulse" />
          <span className="text-xs font-bold uppercase tracking-wider text-gray-200 font-mono">
            Interactive AST Dependency Graph
          </span>
        </div>

        <div className="flex items-center gap-3">
          {hasNodes && (
            <div className="flex items-center gap-2 px-2.5 py-1 rounded-lg bg-gray-950 border border-gray-800 text-[11px] font-mono text-gray-400">
              <span className="text-cyan-400 font-bold">{nodes.length}</span>
              <span>nodes</span>
              <span className="text-gray-600">·</span>
              <span className="text-indigo-400 font-bold">{edges.length}</span>
              <span>edges</span>
            </div>
          )}

          <button
            onClick={toggleDirection}
            title={`Switch to ${direction === 'LR' ? 'Vertical (Top to Bottom)' : 'Horizontal (Left to Right)'} Layout`}
            className="flex items-center gap-1.5 px-3 py-1 rounded-lg bg-gray-800 hover:bg-gray-700 border border-gray-700 text-gray-200 text-xs font-mono font-medium transition-all shadow-sm"
          >
            <ArrowRightLeft className="w-3.5 h-3.5 text-cyan-400" />
            <span>{direction === 'LR' ? 'Horizontal' : 'Vertical'}</span>
          </button>
        </div>
      </div>

      {/* React Flow Viewport */}
      <div className="flex-1 w-full min-h-[440px] relative">
        {hasNodes ? (
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            nodeTypes={nodeTypes}
            fitView
            minZoom={0.15}
            maxZoom={1.8}
            defaultEdgeOptions={{
              type: 'smoothstep',
              animated: true,
            }}
          >
            <Controls className="bg-gray-900/90 border border-gray-800 text-white rounded-xl overflow-hidden shadow-xl" />
            <MiniMap
              nodeColor={(node) => (node.data?.language === 'external' ? '#A855F7' : '#06B6D4')}
              maskColor="rgba(10, 14, 26, 0.85)"
              className="bg-gray-950/90 border border-gray-800 rounded-xl overflow-hidden shadow-2xl"
            />
            <Background color="#1E293B" gap={24} size={1.2} />
          </ReactFlow>
        ) : (
          <div className="flex flex-col items-center justify-center h-full py-16 gap-3 text-center">
            <Compass className="w-10 h-10 text-gray-600 animate-spin" style={{ animationDuration: '10s' }} />
            <p className="text-xs font-mono text-gray-400">
              No dependency graph nodes found for this repository.
            </p>
            <p className="text-[11px] text-gray-600 max-w-xs">
              Ensure the repository has source code files and run an analysis to generate the AST graph.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
