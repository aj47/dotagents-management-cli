import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Power, Terminal, Cpu, Database, Zap, BookOpen, Layers, Activity } from 'lucide-react';

const StatusBadge = ({ status }: { status: string }) => {
  const activeStatuses = ['in-progress', 'in_progress', 'active', 'connected'];
  const isActive = activeStatuses.includes(status);

  return (
    <div className={`font-mono text-[10px] uppercase px-2 py-1 border flex items-center gap-2 w-max
      ${isActive
        ? 'border-[var(--color-accent-secondary)] text-[var(--color-accent-secondary)] bg-[var(--color-accent-secondary)]/10'
        : 'border-[var(--color-text-muted)] text-[var(--color-text-muted)] bg-[var(--color-surface)]'}`}>
      <span className={`inline-block w-1.5 h-1.5 rounded-full ${isActive ? 'bg-current animate-pulse' : 'bg-current opacity-50'}`} />
      {status.replace('_', '-')}
    </div>
  );
};

const ScopeBadge = ({ scope }: { scope: string }) => {
  const isGlobal = scope === 'global';
  return (
    <div className={`font-mono text-[10px] uppercase px-2 py-1 border border-[var(--color-border)] w-max
      ${isGlobal ? 'text-[var(--color-accent-primary)]' : 'text-[var(--color-text-main)]'}`}>
      {scope || 'unknown'}
    </div>
  );
};

export default function App() {
  const [data, setData] = useState<{
    agents: any[];
    skills: any[];
    tasks: any[];
    mcpServers: any[];
    memories: any[];
  } | null>(null);

  const [activeTab, setActiveTab] = useState<'all' | 'agents' | 'skills' | 'tasks' | 'mcpServers' | 'memories'>('all');

  const handleToggle = async (type: string, id: string, isEnabled: boolean) => {
    const action = isEnabled ? 'disable' : 'enable';
    try {
      const res = await fetch(`/api/resources/${type}/${id}/${action}`, { method: 'POST' });
      if (res.ok) {
        fetch('/api/resources').then(r => r.json()).then(setData).catch(console.error);
      }
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    fetch('/api/resources')
      .then(res => res.json())
      .then(setData)
      .catch(console.error);
  }, []);

  if (!data) return <div className="p-8 text-[var(--color-text-main)] font-mono animate-pulse">Initializing Control Plane...</div>;

  const resourceGroups = [
    { key: 'agents', title: 'Agents', icon: Cpu, items: data.agents, type: 'agent' },
    { key: 'skills', title: 'Skills', icon: BookOpen, items: data.skills, type: 'skill' },
    { key: 'tasks', title: 'Tasks', icon: Activity, items: data.tasks, type: 'task' },
    { key: 'mcpServers', title: 'MCP Servers', icon: Terminal, items: data.mcpServers, type: 'mcp-server' },
    { key: 'memories', title: 'Memories', icon: Database, items: data.memories, type: 'memory' }
  ];

  return (
    <div className="min-h-screen bg-[var(--color-base)] text-[var(--color-text-main)] p-4 md:p-8 lg:p-12 overflow-x-hidden selection:bg-[var(--color-accent-primary)] selection:text-white">

      <header className="mb-12 border-b-2 border-[var(--color-border)] pb-8 flex flex-col md:flex-row justify-between items-start md:items-end gap-6">
        <div>
          <h1 className="text-4xl md:text-6xl font-display font-black tracking-tighter uppercase leading-[0.85] text-[var(--color-text-main)] flex items-center gap-4">
            <Layers className="text-[var(--color-accent-primary)] w-12 h-12 md:w-16 md:h-16" />
            <div>
              dot<span className="text-[var(--color-accent-primary)]">agents</span><br />
              <span className="text-[var(--color-text-muted)] text-2xl md:text-4xl">control plane</span>
            </div>
          </h1>
        </div>

        <div className="flex flex-col md:items-end gap-4">
          <div className="flex flex-wrap gap-2 font-mono text-xs uppercase">
            <div className="border-2 border-[var(--color-accent-secondary)] text-[var(--color-accent-secondary)] px-3 py-1.5 flex items-center gap-2 font-bold bg-[var(--color-accent-secondary)]/10">
              <span className="w-2 h-2 bg-current rounded-full animate-pulse" /> System Online
            </div>
            <div className="border-2 border-[var(--color-border)] px-3 py-1.5 bg-[var(--color-text-main)] text-[var(--color-base)] font-bold flex items-center gap-2">
              <Zap size={14} /> Master Override
            </div>
          </div>
        </div>
      </header>

      {/* Tabs */}
      <div className="flex flex-wrap gap-2 mb-8 font-mono text-sm uppercase">
        <button
          onClick={() => setActiveTab('all')}
          className={`px-4 py-2 border-2 transition-all ${activeTab === 'all' ? 'border-[var(--color-text-main)] bg-[var(--color-text-main)] text-[var(--color-base)] font-bold' : 'border-[var(--color-border)] hover:border-[var(--color-text-muted)]'}`}
        >
          All Resources
        </button>
        {resourceGroups.map(g => (
          <button
            key={g.key}
            onClick={() => setActiveTab(g.key as any)}
            className={`px-4 py-2 border-2 transition-all flex items-center gap-2 ${activeTab === g.key ? 'border-[var(--color-text-main)] bg-[var(--color-text-main)] text-[var(--color-base)] font-bold' : 'border-[var(--color-border)] hover:border-[var(--color-text-muted)]'}`}
          >
            <g.icon size={16} />
            {g.title} <span className="opacity-50">[{g.items.length}]</span>
          </button>
        ))}
      </div>

      <div className="flex flex-col gap-12">
        <AnimatePresence mode="popLayout">
          {resourceGroups.filter(g => activeTab === 'all' || activeTab === g.key).map((group) => (
            <motion.div
              key={group.key}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              className="flex flex-col gap-4"
            >
              <h2 className="text-2xl font-display font-bold uppercase text-[var(--color-text-muted)] flex items-center gap-3 border-b border-[var(--color-border)] pb-2">
                <group.icon size={24} className="text-[var(--color-accent-primary)]" />
                {group.title}
              </h2>

              {group.items.length === 0 ? (
                <div className="p-8 border-2 border-dashed border-[var(--color-border)] text-[var(--color-text-muted)] font-mono text-center uppercase text-sm">
                  No {group.title.toLowerCase()} found in registry
                </div>
              ) : (
                <div className="grid grid-cols-1 gap-3">
                  {group.items.map((item) => {
                    const activeStatuses = ['in-progress', 'in_progress', 'active', 'connected'];
                    const isEnabled = activeStatuses.includes(item.status);

                    return (
                      <div
                        key={item.id}
                        className={`group p-4 border-2 transition-all duration-300 flex flex-col md:flex-row md:items-center justify-between gap-4
                          ${isEnabled ? 'border-[var(--color-border)] bg-[var(--color-surface)] hover:border-[var(--color-text-muted)]' : 'border-dashed border-[var(--color-border)] bg-transparent opacity-70 hover:opacity-100'}`}
                      >
                        <div className="flex flex-col gap-1 md:w-1/3">
                          <h3 className="font-bold text-lg uppercase tracking-tight truncate" title={item.name || item.title}>
                            {item.name || item.title}
                          </h3>
                          <p className="font-mono text-xs text-[var(--color-text-muted)] truncate">
                            ID: {item.id}
                          </p>
                        </div>

                        <div className="flex items-center gap-4 flex-wrap md:w-1/3">
                          <ScopeBadge scope={item.scope} />
                          <StatusBadge status={item.status} />
                        </div>

                        <div className="flex items-center gap-6 justify-end md:w-1/3">
                          {item.type && <span className="font-mono text-xs text-[var(--color-text-muted)] uppercase hidden xl:block">TYPE: {item.type}</span>}

                          <button
                            onClick={() => handleToggle(group.type, item.id, isEnabled)}
                            className={`flex items-center gap-2 px-4 py-2 border-2 font-mono text-sm uppercase font-bold transition-all
                              ${isEnabled
                                ? 'border-[var(--color-text-muted)] text-[var(--color-text-main)] hover:border-[var(--color-accent-primary)] hover:text-[var(--color-accent-primary)]'
                                : 'border-dashed border-[var(--color-text-muted)] text-[var(--color-text-muted)] hover:border-[var(--color-accent-secondary)] hover:text-[var(--color-accent-secondary)] hover:border-solid'}`}
                          >
                            <Power size={16} />
                            {isEnabled ? 'Disable' : 'Enable'}
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </motion.div>
          ))}
        </AnimatePresence>
      </div>

    </div>
  );
}
