import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Power, Terminal, Cpu, Database, Zap, BookOpen, Layers, Activity, RefreshCw } from 'lucide-react';

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
    <div className="min-h-screen bg-[var(--color-base)] text-[var(--color-text-main)] p-4 md:p-8 lg:p-12 overflow-x-hidden selection:bg-[var(--color-accent-primary)] selection:text-white">

      <header className="mb-12 border-b-2 border-[var(--color-border)] pb-8 flex flex-col md:flex-row justify-between items-start md:items-end gap-6">
        <div>
          <h1 className="text-4xl md:text-6xl font-display font-black tracking-tighter leading-[0.85] text-[var(--color-text-main)] flex items-center gap-4">
            <Layers className="text-[var(--color-accent-primary)] w-12 h-12 md:w-16 md:h-16" />
            <div>
              .<span className="text-[var(--color-accent-primary)]">agents</span>/<br />
              <span className="uppercase text-[var(--color-text-muted)] text-2xl md:text-4xl">control plane</span>
            </div>
          </h1>
        </div>

        <div className="flex flex-col md:items-end gap-4">
          <div className="flex flex-wrap gap-2 font-mono text-xs uppercase">
            <button
              onClick={handleSync}
              disabled={syncing}
              className={`border-2 px-3 py-1.5 flex items-center gap-2 font-bold transition-all
                ${syncing
                  ? 'border-[var(--color-text-muted)] text-[var(--color-text-muted)]'
                  : 'border-[var(--color-accent-secondary)] text-[var(--color-base)] bg-[var(--color-accent-secondary)] hover:bg-transparent hover:text-[var(--color-accent-secondary)]'}`}
            >
              <RefreshCw size={14} className={syncing ? "animate-spin" : ""} />
              {syncing ? 'Syncing...' : 'Sync Now'}
            </button>
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
              <div className="flex items-center justify-between border-b border-[var(--color-border)] pb-2">
                <h2 className="text-2xl font-display font-bold uppercase text-[var(--color-text-muted)] flex items-center gap-3">
                  <group.icon size={24} className="text-[var(--color-accent-primary)]" />
                  {group.title}
                </h2>
                {group.items.length > 0 && (
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleToggleAll(group.type, group.items, true)}
                      className="px-3 py-1 border border-dashed border-[var(--color-text-muted)] text-[var(--color-text-muted)] font-mono text-xs uppercase hover:border-solid hover:border-[var(--color-accent-secondary)] hover:text-[var(--color-accent-secondary)] transition-colors"
                    >
                      Enable All
                    </button>
                    <button
                      onClick={() => handleToggleAll(group.type, group.items, false)}
                      className="px-3 py-1 border border-[var(--color-text-muted)] text-[var(--color-text-main)] font-mono text-xs uppercase hover:border-[var(--color-accent-primary)] hover:text-[var(--color-accent-primary)] transition-colors"
                    >
                      Disable All
                    </button>
                  </div>
                )}
              </div>

              {group.items.length === 0 ? (
                <div className="p-8 border-2 border-dashed border-[var(--color-border)] text-[var(--color-text-muted)] font-mono text-center uppercase text-sm">
                  No {group.title.toLowerCase()} found in registry
                </div>
              ) : (
                <div className="columns-1 md:columns-2 lg:columns-3 gap-6 space-y-6">
                  {group.items.map((item) => {
                    const activeStatuses = ['in-progress', 'in_progress', 'active', 'connected'];
                    const isEnabled = activeStatuses.includes(item.status);

                    return (
                      <div
                        key={item.id}
                        className={`group p-6 flex flex-col gap-6
                          ${isEnabled ? 'brutal-card' : 'brutal-card-disabled'}`}
                      >
                        <div className="flex flex-col gap-2">
                          <div className="flex justify-between items-start gap-4">
                            <h3 className="font-bold text-xl uppercase tracking-tight break-words" title={item.name || item.title}>
                              {item.name || item.title}
                            </h3>
                            {item.type && <span className="font-mono text-[10px] bg-[var(--color-surface)] px-2 py-1 border border-[var(--color-border)] text-[var(--color-text-muted)] uppercase shrink-0">TYPE: {item.type}</span>}
                          </div>
                          <p className="font-mono text-xs text-[var(--color-text-muted)] break-all">
                            ID: {item.id}
                          </p>
                        </div>

                        <div className="flex items-center gap-3 flex-wrap">
                          <ScopeBadge scope={item.scope} />
                          <StatusBadge status={item.status} />
                        </div>

                        <div className="flex items-center justify-end mt-2">
                          <button
                            onClick={() => handleToggle(group.type, item.id, isEnabled)}
                            className={`flex items-center gap-2 px-5 py-2.5 border-2 font-mono text-sm uppercase font-bold transition-all
                              ${isEnabled
                                ? 'border-[var(--color-text-main)] text-[var(--color-text-main)] bg-transparent hover:border-[var(--color-accent-primary)] hover:text-[var(--color-accent-primary)]'
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

      <div className="fixed bottom-0 left-0 w-full overflow-hidden bg-[var(--color-accent-primary)] text-[var(--color-base)] font-mono text-sm font-bold uppercase py-1.5 z-[100] flex whitespace-nowrap border-t-[var(--brutal-border)] border-[var(--color-border)] shadow-[0_-4px_0_0_var(--color-border)]">
        <div className="flex animate-marquee min-w-max">
          {[...Array(15)].map((_, i) => (
            <span key={i} className="mx-4 flex items-center gap-4">
              <Zap size={14} className="fill-current" /> SYSTEM ONLINE // DOTAGENTS CLI ACTIVE // NOISE INJECTED // AESTHETICS ELEVATED
            </span>
          ))}
        </div>
      </div>

    </div>
  );
}
