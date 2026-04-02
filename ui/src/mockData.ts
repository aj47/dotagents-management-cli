export const agents = [
  { id: 'ag-1', name: 'Scaffold Frontend Project', type: 'task-loop', status: 'in-progress' },
  { id: 'ag-2', name: 'Database Migrator', type: 'background', status: 'idle' },
  { id: 'ag-3', name: 'Test Runner', type: 'verifier', status: 'completed' }
];

export const skills = [
  { id: 'sk-1', name: 'frontend-design', description: 'Creates distinctive UI with bold aesthetics' },
  { id: 'sk-2', name: 'agent-skill-creation', description: 'Teaches how to create new Agent Skills' },
  { id: 'sk-3', name: 'github-issue', description: 'GitHub Issue creator for aj47/dotagents-mono' }
];

export const tasks = [
  { id: 'ts-1', title: 'Scaffold Frontend Project', status: 'in_progress', agent: 'ag-1' },
  { id: 'ts-2', title: 'Setup CI/CD Pipeline', status: 'not_started', agent: null },
  { id: 'ts-3', title: 'Write E2E tests for auth', status: 'completed', agent: 'ag-3' }
];

export const mcpServers = [
  { id: 'mcp-1', name: 'workspace-mcp', status: 'connected' },
  { id: 'mcp-2', name: 'github-mcp', status: 'disconnected' },
  { id: 'mcp-3', name: 'db-mcp', status: 'connected' }
];

export const memories = [
  { id: 'mem-1', name: 'Project Guidelines', size: '12 KB', status: 'active' },
  { id: 'mem-2', name: 'User Preferences', size: '4 KB', status: 'active' },
  { id: 'mem-3', name: 'Legacy API Keys', size: '1 KB', status: 'archived' }
];
