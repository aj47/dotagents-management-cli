import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Power, Terminal, Cpu, Database, Zap, BookOpen, Layers, Activity, RefreshCw } from 'lucide-react';

const StatusBadge = ({ status }: { status: string }) => {
  const activeStatuses = ['in-progress', 'in_progress', 'active', 'connected'];
  const isActive = activeStatuses.includes(status);

  return (
    <div className={`font-mono text-[10px] uppercase px-1 py-0.5 border flex items-center gap-1 w-max
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
    <div className={`font-mono text-[10px] uppercase px-1 py-0.5 border border-[var(--color-border)] w-max
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
  const [syncing, setSyncing] = useState(false);

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

  const handleToggleAll = async (groupType: string, items: any[], enable: boolean) => {
    const action = enable ? 'enable' : 'disable';
    const activeStatuses = ['in-progress', 'in_progress', 'active', 'connected'];

    const itemsToToggle = items.filter(item => {
        const isEnabled = activeStatuses.includes(item.status);
        return isEnabled !== enable;
    });

    if (itemsToToggle.length === 0) return;

    try {
      await Promise.all(itemsToToggle.map(item =>
        fetch(`/api/resources/${groupType}/${item.id}/${action}`, { method: 'POST' })
      ));
      const res = await fetch('/api/resources');
      setData(await res.json());
    } catch(e) {
      console.error(e);
    }
  };

  const handleSync = async () => {
    setSyncing(true);
    try {
      await fetch('/api/sync', { method: 'POST' });
      const r = await fetch('/api/resources');
      setData(await r.json());
    } catch(e) {
      console.error(e);
    }
    setSyncing(false);
  };

  useEffect(() => {
    fetch('/api/resources')
      .then(res => res.json())
      .then(setData)
      .catch(console.error);
  }, []);

  if (!data) return <div className="p-8 text-[var(--color-text-main)] font-mono animate-pulse">Initializing Control Plane...</div>;

  const resourceGroups = [
    { key: 'skills', title: 'Skills', icon: BookOpen, items: data.skills, type: 'skill' },
    { key: 'agents', title: 'Agents', icon: Cpu, items: data.agents, type: 'agent' },
    { key: 'tasks', title: 'Tasks', icon: Activity, items: data.tasks, type: 'task' },
    { key: 'mcpServers', title: 'MCP Servers', icon: Terminal, items: data.mcpServers, type: 'mcp-server' },
    { key: 'memories', title: 'Memories', icon: Database, items: data.memories, type: 'memory' }
  ];

  return (
    <div className="min-h-screen bg-[var(--color-base)] text-[var(--color-text-main)] p-2 md:p-4 lg:p-6 overflow-x-hidden selection:bg-[var(--color-accent-primary)] selection:text-white">

      <header className="mb-6 border-b border-[var(--color-border)] pb-4 flex flex-col md:flex-row justify-between items-start md:items-end gap-4">
        <div>
          <h1 className="text-2xl md:text-4xl font-display font-black tracking-tighter leading-[0.85] text-[var(--color-text-main)] flex items-center gap-3">
            <Layers className="text-[var(--color-accent-primary)] w-8 h-8 md:w-10 md:h-10" />
            <div>
              .<span className="text-[var(--color-accent-primary)]">agents</span>/<br />
              <span className="uppercase text-[var(--color-text-muted)] text-lg md:text-2xl">control plane</span>
            </div>
          </h1>
        </div>

        <div className="flex flex-col md:items-end gap-3">
          <div className="flex flex-wrap gap-1.5 font-mono text-[10px] md:text-xs uppercase">
            <button
              onClick={handleSync}
              disabled={syncing}
              className={`border px-2 py-1 flex items-center gap-1.5 font-bold transition-all
                ${syncing
                  ? 'border-[var(--color-text-muted)] text-[var(--color-text-muted)]'
                  : 'border-[var(--color-accent-secondary)] text-[var(--color-base)] bg-[var(--color-accent-secondary)] hover:bg-transparent hover:text-[var(--color-accent-secondary)]'}`}
            >
              <RefreshCw size={12} className={syncing ? "animate-spin" : ""} />
              {syncing ? 'Syncing...' : 'Sync Now'}
            </button>
            <div className="border border-[var(--color-accent-secondary)] text-[var(--color-accent-secondary)] px-2 py-1 flex items-center gap-1.5 font-bold bg-[var(--color-accent-secondary)]/10">
              <span className="w-1.5 h-1.5 bg-current rounded-full animate-pulse" /> System Online
            </div>
            <div className="border border-[var(--color-border)] px-2 py-1 bg-[var(--color-text-main)] text-[var(--color-base)] font-bold flex items-center gap-1.5">
              <Zap size={12} /> Master Override
            </div>
          </div>
        </div>
      </header>

      {/* Tabs */}
      <div className="flex flex-wrap gap-1.5 mb-4 font-mono text-xs md:text-sm uppercase">
        <button
          onClick={() => setActiveTab('all')}
          className={`px-3 py-1.5 border transition-all ${activeTab === 'all' ? 'border-[var(--color-text-main)] bg-[var(--color-text-main)] text-[var(--color-base)] font-bold' : 'border-[var(--color-border)] hover:border-[var(--color-text-muted)]'}`}
        >
          All Resources
        </button>
        {resourceGroups.map(g => (
          <button
            key={g.key}
            onClick={() => setActiveTab(g.key as any)}
            className={`px-3 py-1.5 border transition-all flex items-center gap-1.5 ${activeTab === g.key ? 'border-[var(--color-text-main)] bg-[var(--color-text-main)] text-[var(--color-base)] font-bold' : 'border-[var(--color-border)] hover:border-[var(--color-text-muted)]'}`}
          >
            <g.icon size={14} />
            {g.title} <span className="opacity-50">[{g.items.length}]</span>
          </button>
        ))}
      </div>

      <div className="flex flex-col gap-6">
        <AnimatePresence mode="popLayout">
          {resourceGroups.filter(g => activeTab === 'all' || activeTab === g.key).map((group) => (
            <motion.div
              key={group.key}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="flex flex-col gap-3"
            >
              <div className="flex items-center justify-between border-b border-[var(--color-border)] pb-2">
                <h2 className="text-lg md:text-xl font-display font-bold uppercase text-[var(--color-text-muted)] flex items-center gap-2">
                  <group.icon size={18} className="text-[var(--color-accent-primary)]" />
                  {group.title}
                </h2>
                {group.items.length > 0 && (
                  <div className="flex gap-1.5">
                    <button
                      onClick={() => handleToggleAll(group.type, group.items, true)}
                      className="px-2 py-0.5 border border-dashed border-[var(--color-text-muted)] text-[var(--color-text-muted)] font-mono text-[10px] uppercase hover:border-solid hover:border-[var(--color-accent-secondary)] hover:text-[var(--color-accent-secondary)] transition-colors"
                    >
                      Enable All
                    </button>
                    <button
                      onClick={() => handleToggleAll(group.type, group.items, false)}
                      className="px-2 py-0.5 border border-[var(--color-text-muted)] text-[var(--color-text-main)] font-mono text-[10px] uppercase hover:border-[var(--color-accent-primary)] hover:text-[var(--color-accent-primary)] transition-colors"
                    >
                      Disable All
                    </button>
                  </div>
                )}
              </div>

              {group.items.length === 0 ? (
                <div className="p-4 border border-dashed border-[var(--color-border)] text-[var(--color-text-muted)] font-mono text-center uppercase text-xs rounded-lg">
                  No {group.title.toLowerCase()} found in registry
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 md:gap-4">
                  {group.items.map((item) => {
                    const activeStatuses = ['in-progress', 'in_progress', 'active', 'connected'];
                    const isEnabled = activeStatuses.includes(item.status);

                    return (
                      <div
                        key={item.id}
                        className={`group p-2 md:p-2.5 flex flex-col gap-2
                          ${isEnabled ? 'brutal-card' : 'brutal-card-disabled'}`}
                      >
                        <div className="flex flex-col gap-1">
                          <div className="flex justify-between items-start gap-1.5">
                            <h3 className="font-bold text-sm md:text-base uppercase tracking-tight break-words" title={item.name || item.title}>
                              {item.name || item.title}
                            </h3>
                            {item.type && <span className="font-mono text-[9px] bg-[var(--color-surface)] px-1 py-0.5 border border-[var(--color-border)] text-[var(--color-text-muted)] uppercase shrink-0">TYPE: {item.type}</span>}
                          </div>
                          <p className="font-mono text-[10px] text-[var(--color-text-muted)] break-all leading-tight">
                            ID: {item.id}
                          </p>
                        </div>

                        <div className="flex items-center gap-1.5 flex-wrap">
                          <ScopeBadge scope={item.scope} />
                          <StatusBadge status={item.status} />
                        </div>

                        <div className="flex items-center justify-end mt-0.5">
                          <button
                            onClick={() => handleToggle(group.type, item.id, isEnabled)}
                            className={`flex items-center gap-1 px-2 py-1 border font-mono text-[10px] uppercase font-bold transition-all
                              ${isEnabled
                                ? 'border-[var(--color-text-main)] text-[var(--color-text-main)] bg-transparent hover:border-[var(--color-accent-primary)] hover:text-[var(--color-accent-primary)]'
                                : 'border-dashed border-[var(--color-text-muted)] text-[var(--color-text-muted)] hover:border-[var(--color-accent-secondary)] hover:text-[var(--color-accent-secondary)] hover:border-solid'}`}
                          >
                            <Power size={12} />
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
