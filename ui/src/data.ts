export type ResourceStatus = 'enabled' | 'disabled' | 'unknown';

export interface BaseResource {
  id: string;
  name: string;
  description?: string;
  status: ResourceStatus;
  updatedAt: string;
}

export interface Skill extends BaseResource {
  type: 'skill';
  version: string;
}

export interface Agent extends BaseResource {
  type: 'agent';
  model: string;
  specialist: string;
}

export interface Task extends BaseResource {
  type: 'task';
  priority: 'low' | 'medium' | 'high';
}

export interface Memory extends BaseResource {
  type: 'memory';
  size: number;
}

export interface McpServer extends BaseResource {
  type: 'mcp-server';
  url: string;
}

export const MOCK_SKILLS: Skill[] = [
  { id: 'frontend-design', name: 'Frontend Design', description: 'Creates distinctive UI components', status: 'enabled', updatedAt: '2026-04-01T10:00:00Z', type: 'skill', version: '1.2.0' },
  { id: 'aj-brand-voice', name: 'AJ Brand Voice', description: 'Generates content in AJ\'s tone', status: 'enabled', updatedAt: '2026-03-15T14:30:00Z', type: 'skill', version: '2.0.1' },
  { id: 'legacy-data-parser', name: 'Legacy Parser', description: 'Parses old XML formats', status: 'disabled', updatedAt: '2025-11-20T09:15:00Z', type: 'skill', version: '0.9.5' },
];

export const MOCK_AGENTS: Agent[] = [
  { id: 'agent-1a2b', name: 'Implementor', description: 'Writes the code based on spec', status: 'enabled', updatedAt: '2026-04-02T08:00:00Z', type: 'agent', model: 'gemini-3.1-pro-preview', specialist: 'implementor' },
  { id: 'agent-3c4d', name: 'Reviewer', description: 'Reviews code for best practices', status: 'enabled', updatedAt: '2026-04-02T08:05:00Z', type: 'agent', model: 'gemini-3.1-pro-preview', specialist: 'reviewer' },
  { id: 'agent-5e6f', name: 'Old Bot', description: 'Deprecated bot', status: 'disabled', updatedAt: '2025-12-01T11:00:00Z', type: 'agent', model: 'gpt-3.5-turbo', specialist: 'general' },
];

export const MOCK_TASKS: Task[] = [
  { id: 'task-c890', name: 'Scaffold Frontend Project', description: 'Create Vite React app', status: 'enabled', updatedAt: '2026-04-01T09:00:00Z', type: 'task', priority: 'high' },
  { id: 'task-8e78', name: 'Implement Resource Views', description: 'Build out UI components', status: 'enabled', updatedAt: '2026-04-02T09:30:00Z', type: 'task', priority: 'high' },
];

export const MOCK_MEMORIES: Memory[] = [
  { id: 'mem-001', name: 'Project Guidelines', description: 'Rules for coding style', status: 'enabled', updatedAt: '2026-01-10T12:00:00Z', type: 'memory', size: 1024 },
  { id: 'mem-002', name: 'Old Architecture', description: 'Docs for v1', status: 'disabled', updatedAt: '2025-06-05T15:45:00Z', type: 'memory', size: 4096 },
];

export const MOCK_MCP_SERVERS: McpServer[] = [
  { id: 'mcp-workspace', name: 'Workspace MCP', description: 'Local file and note access', status: 'enabled', updatedAt: '2026-04-01T08:00:00Z', type: 'mcp-server', url: 'stdio://workspace' },
  { id: 'mcp-github', name: 'GitHub MCP', description: 'Access to GitHub API', status: 'enabled', updatedAt: '2026-03-20T10:00:00Z', type: 'mcp-server', url: 'https://mcp.github.com' },
];

export const ALL_RESOURCES = [
  ...MOCK_SKILLS,
  ...MOCK_AGENTS,
  ...MOCK_TASKS,
  ...MOCK_MEMORIES,
  ...MOCK_MCP_SERVERS,
];
