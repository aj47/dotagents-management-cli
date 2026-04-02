import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { CheckCircle, CircleDashed, Play, Terminal, Cpu, Database, Zap, Palette } from 'lucide-react';
import { agents, skills, tasks, mcpServers, memories } from './mockData';

const getVariants = (theme: string) => {
  if (theme === 'theme-luxury') {
    return {
      container: {
        hidden: { opacity: 0 },
        visible: { opacity: 1, transition: { staggerChildren: 0.15, delayChildren: 0.2 } }
      },
      block: {
        hidden: { y: 10, opacity: 0, scale: 0.98 },
        visible: { y: 0, opacity: 1, scale: 1, transition: { type: 'tween', duration: 0.8, ease: [0.25, 1, 0.5, 1] } }
      }
    };
  }
  if (theme === 'theme-chaos') {
    return {
      container: {
        hidden: { opacity: 0 },
        visible: { opacity: 1, transition: { staggerChildren: 0.05, delayChildren: 0 } }
      },
      block: {
        hidden: { y: -50, x: -50, opacity: 0, scale: 0.8, rotate: -5 },
        visible: { y: 0, x: 0, opacity: 1, scale: 1, rotate: 0, transition: { type: 'spring', stiffness: 300, damping: 10 } }
      }
    };
  }
  if (theme === 'theme-retro') {
    return {
      container: {
        hidden: { opacity: 0 },
        visible: { opacity: 1, transition: { staggerChildren: 0.1, delayChildren: 0.1 } }
      },
      block: {
        hidden: { opacity: 0, scale: 1 },
        visible: { opacity: 1, scale: 1, transition: { type: 'tween', duration: 0.1 } } // Instant appearance
      }
    };
  }
  // brutal
  return {
    container: {
      hidden: { opacity: 0 },
      visible: { opacity: 1, transition: { staggerChildren: 0.08, delayChildren: 0.1 } }
    },
    block: {
      hidden: { y: 20, opacity: 0, scale: 0.95 },
      visible: { y: 0, opacity: 1, scale: 1, transition: { type: 'spring', stiffness: 120, damping: 14 } }
    }
  };
};

const StatusDot = ({ active }: { active: boolean }) => (
  <span className={`inline-block w-2 h-2 rounded-full ${active ? 'bg-[var(--color-accent-secondary)] shadow-[0_0_8px_var(--color-accent-secondary)] animate-pulse' : 'bg-[var(--color-border)]'}`} />
);

const themes = [
  { id: 'theme-brutal', label: 'Brutal' },
  { id: 'theme-luxury', label: 'Luxury' },
  { id: 'theme-chaos', label: 'Chaos' },
  { id: 'theme-retro', label: 'Retro' }
];

export default function App() {
  const [theme, setTheme] = useState(() => localStorage.getItem('app-theme') || 'theme-brutal');
  const variants = getVariants(theme);

  useEffect(() => {
    localStorage.setItem('app-theme', theme);
    document.documentElement.className = theme;
  }, [theme]);

  return (
    <div className="min-h-screen bg-[var(--color-base)] text-[var(--color-text-main)] p-4 md:p-8 lg:p-12 overflow-x-hidden selection:bg-[var(--color-accent-primary)] selection:text-white transition-colors duration-500">

      <header className="mb-16 border-b border-[var(--color-border)] pb-8 flex flex-col md:flex-row justify-between items-start md:items-end gap-6">
        <motion.div initial={{ x: -50, opacity: 0 }} animate={{ x: 0, opacity: 1 }} transition={{ duration: 0.8, ease: "easeOut" }}>
          <h1 className="text-6xl md:text-8xl font-display font-black tracking-tighter uppercase leading-[0.85] text-[var(--color-text-main)]">
            dot<span className="text-[var(--color-accent-primary)]">agents</span><br />
            <span className="text-[var(--color-text-muted)] text-4xl md:text-6xl">system</span>
          </h1>
          <p className="font-mono text-[var(--color-text-muted)] mt-4 uppercase tracking-[0.2em] text-sm">
            management console // v1.0
          </p>
        </motion.div>

        <motion.div
          className="flex flex-col md:items-end gap-4"
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.5 }}
        >
          <div className="flex flex-wrap gap-2 font-mono text-xs uppercase items-center">
            <Palette size={14} className="text-[var(--color-text-muted)] mr-1" />
            {themes.map(t => (
              <button
                key={t.id}
                onClick={() => setTheme(t.id)}
                className={`px-2 py-1 border transition-colors cursor-pointer ${
                  theme === t.id
                    ? 'border-[var(--color-accent-primary)] bg-[var(--color-text-main)] text-[var(--color-base)] font-bold'
                    : 'border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-text-main)] hover:border-[var(--color-text-main)]'
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>
          <div className="flex flex-wrap gap-2 font-mono text-xs uppercase">
            <div className="border border-[var(--color-border)] px-3 py-1 flex items-center gap-2">
              <StatusDot active={true} /> System Online
            </div>
            <div className="border border-[var(--color-border)] px-3 py-1 bg-[var(--color-text-main)] text-[var(--color-base)] font-bold">
              <Zap size={14} className="inline mr-1" /> Override
            </div>
          </div>
        </motion.div>
      </header>

      <motion.div
        className="grid grid-cols-1 md:grid-cols-12 gap-6 auto-rows-[minmax(100px,auto)]"
        variants={variants.container}
        initial="hidden"
        animate="visible"
        key={theme} // Force re-animation when theme changes
      >
        {/* AGENTS: Large striking block */}
        <motion.div variants={variants.block} className="md:col-span-8 lg:col-span-5 brutal-box p-6 flex flex-col gap-6 relative overflow-hidden group">
          <div className="absolute -right-10 -top-10 opacity-5 group-hover:opacity-10 transition-opacity duration-500">
            <Cpu size={240} />
          </div>

          <div className="flex items-center justify-between border-b border-[var(--color-border)] pb-2 relative z-10">
            <h2 className="text-2xl font-display text-[var(--color-accent-primary)] m-0">Agents</h2>
            <span className="font-mono text-xs text-[var(--color-text-muted)]">[{agents.length} active]</span>
          </div>

          <div className="grid grid-cols-1 gap-4 relative z-10">
            {agents.map((agent, i) => (
              <motion.div
                key={agent.id}
                whileHover={{ x: 10 }}
                className={`p-4 border-l-4 flex justify-between items-center bg-[var(--color-surface)] ${agent.status === 'in-progress' ? 'border-[var(--color-accent-secondary)]' : 'border-[var(--color-border)]'}`}
              >
                <div>
                  <h3 className="font-bold text-xl uppercase tracking-tight">{agent.name}</h3>
                  <p className="font-mono text-xs text-[var(--color-text-muted)] mt-1">{agent.id} // {agent.type}</p>
                </div>
                <div className="font-mono text-[10px] uppercase px-2 py-1 bg-[var(--color-base)] border border-[var(--color-border)]">
                  {agent.status}
                </div>
              </motion.div>
            ))}
          </div>
        </motion.div>

        {/* TASKS: Tall dense column */}
        <motion.div variants={variants.block} className="md:col-span-4 lg:col-span-3 brutal-box p-6 bg-[var(--color-surface-hover)] border-[var(--color-accent-secondary)]">
          <div className="flex items-center gap-2 mb-6">
            <Terminal className="text-[var(--color-accent-secondary)]" size={24} />
            <h2 className="text-xl font-display m-0">Task Queue</h2>
          </div>

          <div className="flex flex-col gap-3">
            {tasks.map(task => (
              <div key={task.id} className="group cursor-pointer">
                <div className="flex gap-3 items-start">
                  <div className="mt-1">
                    {task.status === 'completed' ? <CheckCircle size={16} className="text-[var(--color-accent-secondary)]" /> :
                     task.status === 'in_progress' ? <Play size={16} className="text-[var(--color-accent-primary)] animate-pulse" /> :
                     <CircleDashed size={16} className="text-[var(--color-text-muted)] group-hover:text-[var(--color-text-main)] transition-colors" />}
                  </div>
                  <div>
                    <div className={`font-mono text-sm leading-tight ${task.status === 'completed' ? 'text-[var(--color-text-muted)] line-through' : 'text-[var(--color-text-main)]'}`}>
                      {task.title}
                    </div>
                    {task.agent && <div className="text-[10px] font-mono text-[var(--color-accent-primary)] mt-1 opacity-80">{'->'} {task.agent}</div>}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </motion.div>

        {/* SKILLS: Horizontal marquee-style or tight grid */}
        <motion.div variants={variants.block} className="md:col-span-12 lg:col-span-4 brutal-box p-6 flex flex-col">
          <h2 className="text-xl font-display border-b border-[var(--color-border)] pb-2 mb-4">Skills Registry</h2>
          <div className="flex flex-wrap gap-2">
            {skills.map((skill) => (
              <motion.div
                key={skill.id}
                whileHover={{ scale: 1.05, backgroundColor: 'var(--color-text-main)', color: 'var(--color-base)' }}
                className="border border-[var(--color-border)] px-3 py-2 transition-colors cursor-crosshair"
              >
                <div className="font-bold text-sm uppercase">{skill.name}</div>
              </motion.div>
            ))}
          </div>
        </motion.div>

        {/* MEMORIES: Abstract floating layout */}
        <motion.div variants={variants.block} className="md:col-span-6 lg:col-span-5 brutal-box p-6 bg-gradient-to-br from-[var(--color-surface)] to-[var(--color-base)] border-t-[var(--color-accent-primary)] border-t-4">
          <div className="flex items-center gap-2 mb-6 text-[var(--color-accent-primary)]">
            <Database size={20} />
            <h2 className="text-xl font-display m-0">Memories</h2>
          </div>
          <div className="space-y-3">
            {memories.map(mem => (
              <div key={mem.id} className="flex justify-between items-center border-b border-dashed border-[var(--color-border)] pb-2">
                <span className="font-mono text-sm">{mem.name}</span>
                <span className="font-mono text-xs text-[var(--color-text-muted)]">{mem.size}</span>
              </div>
            ))}
          </div>
        </motion.div>

        {/* MCP SERVERS: Terminal style readout */}
        <motion.div variants={variants.block} className="md:col-span-6 lg:col-span-7 brutal-box p-0 bg-black overflow-hidden flex flex-col">
          <div className="bg-[var(--color-border)] px-4 py-2 font-mono text-xs text-[var(--color-text-muted)] flex gap-4">
            <span>TERMINAL</span>
            <span>mcp_connect.sh</span>
          </div>
          <div className="p-4 font-mono text-sm flex flex-col gap-2">
            {mcpServers.map((mcp, i) => (
              <motion.div
                key={mcp.id}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 1 + i * 0.2 }}
                className="flex gap-4"
              >
                <span className="text-[var(--color-text-muted)]">{'>'}</span>
                <span className={mcp.status === 'connected' ? 'text-[var(--color-accent-secondary)]' : 'text-red-500'}>
                  [{mcp.status.toUpperCase()}]
                </span>
                <span className="text-[var(--color-text-main)]">{mcp.name}</span>
              </motion.div>
            ))}
            <motion.div
              initial={{ opacity: 0 }} animate={{ opacity: [0, 1, 0] }} transition={{ repeat: Infinity, duration: 1 }}
              className="text-[var(--color-accent-secondary)] mt-2"
            >
              _
            </motion.div>
          </div>
        </motion.div>
      </motion.div>
    </div>
  );
}
