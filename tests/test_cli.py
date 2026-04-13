from __future__ import annotations

import json
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest import mock

from dotagents_management_cli.cli import build_context, build_tui_browser_data, build_tui_categories, cycle_scope, execute, main, supports_rich_tui


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class DotagentsCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()
        self.global_agents = self.root / "global-agents"
        self.env = {
            "DOTAGENTS_GLOBAL_HOME": str(self.global_agents),
            "DOTAGENTS_WORKSPACE_ROOT": str(self.workspace),
        }

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def run_cli(self, *args: str):
        return execute(list(args), cwd=self.workspace, env=self.env)

    def test_disable_and_enable_skill_moves_directory_and_creates_backup(self) -> None:
        skill_dir = self.workspace / ".agents" / "skills" / "writer"
        skill_dir.mkdir(parents=True)
        result = self.run_cli("--workspace", "disable", "skill", "writer")
        self.assertIn("disabled skill", result.human_text)
        self.assertFalse(skill_dir.exists())
        self.assertTrue((self.workspace / ".agents" / ".disabled" / "skills" / "writer").exists())
        backups = list((self.workspace / ".agents" / ".backups").iterdir())
        self.assertTrue(backups)
        self.run_cli("--workspace", "enable", "skill", "writer")
        self.assertTrue(skill_dir.exists())

    def test_disable_and_enable_all_skills_moves_every_skill(self) -> None:
        write(self.workspace / ".agents" / "skills" / "writer" / "README.md", "# writer")
        write(self.workspace / ".agents" / "skills" / "coder" / "README.md", "# coder")

        disable_result = self.run_cli("--workspace", "disable", "all-skills")
        self.assertIn("Disabled 2 items", disable_result.human_text)
        self.assertIn("writer", disable_result.human_text)
        self.assertIn("coder", disable_result.human_text)
        self.assertTrue((self.workspace / ".agents" / ".disabled" / "skills" / "writer").exists())
        self.assertTrue((self.workspace / ".agents" / ".disabled" / "skills" / "coder").exists())

        enable_result = self.run_cli("--workspace", "enable", "all-skills")
        self.assertIn("Enabled 2 items", enable_result.human_text)
        self.assertTrue((self.workspace / ".agents" / "skills" / "writer").exists())
        self.assertTrue((self.workspace / ".agents" / "skills" / "coder").exists())

    def test_show_agent_explains_skill_availability_and_allow_updates_config(self) -> None:
        write(self.global_agents / "skills" / "writer" / "README.md", "# skill")
        write(self.workspace / ".agents" / "agents" / "assistant" / "agent.md", "---\nenabled: true\n---\n")
        write(
            self.workspace / ".agents" / "agents" / "assistant" / "config.json",
            json.dumps({"skillsConfig": {"allSkillsDisabledByDefault": True, "enabledSkillIds": [], "disabledSkillIds": []}}),
        )
        before = self.run_cli("show", "agent", "assistant")
        self.assertIn("not in enabledSkillIds", before.human_text)
        self.run_cli("--workspace", "allow", "skill", "writer", "--agent", "assistant")
        after = self.run_cli("show", "agent", "assistant")
        self.assertIn("available", after.human_text)

    def test_mcp_settings_and_model_commands(self) -> None:
        write(
            self.workspace / ".agents" / "mcp.json",
            json.dumps({
                "mcpServers": {"browser": {"tools": ["open"]}},
                "mcpRuntimeDisabledServers": [],
                "mcpDisabledTools": [],
            }),
        )
        write(self.workspace / ".agents" / "dotagents-settings.json", json.dumps({"ui": {"theme": "dark"}, "apiKey": "secret"}))
        write(self.workspace / ".agents" / "models.json", json.dumps({"default": {"name": "gpt-5"}}))
        self.run_cli("--workspace", "disable", "mcp-server", "browser")
        servers = self.run_cli("--workspace", "list", "mcp-servers")
        self.assertIn("runtime-disabled", servers.human_text)
        self.run_cli("--workspace", "disable", "mcp-tool", "browser.open")
        tools = self.run_cli("--workspace", "list", "mcp-tools")
        self.assertIn("disabled in mcp.json", tools.human_text)
        self.run_cli("--workspace", "set", "setting", "ui.theme", '"light"')
        get_theme = self.run_cli("--workspace", "get", "setting", "ui.theme")
        self.assertIn('"light"', get_theme.human_text)
        self.run_cli("--workspace", "set", "model", "default.provider", '"openai"')
        models = json.loads((self.workspace / ".agents" / "models.json").read_text(encoding="utf-8"))
        self.assertEqual(models["default"]["provider"], "openai")

    def test_doctor_reports_broken_references_and_conflicts(self) -> None:
        write(self.workspace / ".agents" / "agents" / "assistant" / "agent.md", "---\nenabled: false\n---\n")
        write(self.workspace / ".agents" / ".disabled" / "agents" / "assistant" / "README.md", "# disabled")
        write(
            self.workspace / ".agents" / "agents" / "assistant" / "config.json",
            json.dumps({"skillsConfig": {"enabledSkillIds": ["missing-skill"]}}),
        )
        write(self.workspace / ".agents" / "mcp.json", "{not-json}")
        broken_backup = self.workspace / ".agents" / ".backups" / "broken"
        broken_backup.mkdir(parents=True)
        result = self.run_cli("doctor")
        self.assertIn("missing skill", result.human_text)
        self.assertIn("Conflicting state", result.human_text)
        self.assertIn("Malformed `mcp.json`", result.human_text)

    def test_main_without_subcommand_launches_interactive_mode(self) -> None:
        skill_dir = self.workspace / ".agents" / "skills" / "writer"
        skill_dir.mkdir(parents=True)
        answers = iter(["5", "1", "writer", "2", "q"])
        output = StringIO()

        exit_code = main(
            [],
            cwd=self.workspace,
            env=self.env,
            input_fn=lambda prompt: next(answers),
            output_stream=output,
        )

        self.assertEqual(exit_code, 0)
        self.assertIn("manage-dotagents interactive mode", output.getvalue())
        self.assertIn("disabled skill `writer`", output.getvalue())
        self.assertTrue((self.workspace / ".agents" / ".disabled" / "skills" / "writer").exists())

    def test_tui_browser_helpers_are_stable(self) -> None:
        write(self.workspace / ".agents" / "skills" / "writer" / "README.md", "# writer")
        write(self.workspace / ".agents" / "agents" / "assistant" / "agent.md", "---\nenabled: true\n---\n")
        write(self.workspace / ".agents" / "tasks" / "daily" / "task.md", "---\nenabled: true\n---\n")
        write(self.workspace / ".agents" / "mcp.json", json.dumps({"mcpServers": {"browser": {"tools": ["open"]}}}))
        categories = build_tui_categories()
        self.assertEqual(categories[0].key, "skills")
        browser = build_tui_browser_data(build_context(cwd=self.workspace, env=self.env), "workspace")
        self.assertEqual(len(browser.items_by_category["skills"]), 1)
        self.assertEqual(len(browser.items_by_category["agents"]), 1)
        self.assertEqual(len(browser.items_by_category["tasks"]), 1)
        self.assertEqual(len(browser.items_by_category["mcp-servers"]), 1)
        self.assertEqual(cycle_scope("effective"), "workspace")
        self.assertEqual(cycle_scope("workspace"), "global")
        self.assertEqual(cycle_scope("global"), "effective")

    def test_rich_tui_disabled_for_non_tty_streams(self) -> None:
        fake_stdin = mock.Mock()
        fake_stdin.isatty.return_value = False
        with mock.patch("sys.stdin", fake_stdin), mock.patch.dict("os.environ", {"TERM": "xterm-256color"}, clear=False):
            self.assertFalse(supports_rich_tui(input, StringIO()))

    def test_cursor_adapter_sync(self) -> None:
        write(self.workspace / ".agents" / "skills" / "writer" / "SKILL.md", "# writer")
        write(self.workspace / ".agents" / "mcp.json", json.dumps({"mcpServers": {"browser": {"tools": ["open"]}}}))

        # Push to cursor
        push_result = self.run_cli("--workspace", "sync", "--target", "cursor", "--push")
        self.assertIn("Syncing", push_result.human_text)
        cursor_dir = self.workspace / ".cursor"
        self.assertTrue((cursor_dir / "rules" / "writer.mdc").exists())
        self.assertTrue((cursor_dir / "mcp.json").exists())
        mdc_content = (cursor_dir / "rules" / "writer.mdc").read_text(encoding="utf-8")
        self.assertIn("description: Skill writer", mdc_content)
        self.assertIn("# writer", mdc_content)

        # Pull from cursor
        write(cursor_dir / "rules" / "new_skill.mdc", "---\ndescription: test\nglobs: *\n---\n# new rule")
        write(self.workspace / ".cursorrules", "# global rules")

        pull_result = self.run_cli("--workspace", "sync", "--target", "cursor", "--pull")
        self.assertTrue((self.workspace / ".agents" / "skills" / "new_skill" / "SKILL.md").exists())
        self.assertTrue((self.workspace / ".agents" / "skills" / "cursorrules" / "SKILL.md").exists())

        new_skill_content = (self.workspace / ".agents" / "skills" / "new_skill" / "SKILL.md").read_text(encoding="utf-8")
        self.assertEqual(new_skill_content.strip(), "# new rule")

        cursorrules_content = (self.workspace / ".agents" / "skills" / "cursorrules" / "SKILL.md").read_text(encoding="utf-8")
        self.assertEqual(cursorrules_content.strip(), "# global rules")

    def test_auto_sync_mcp_server_add_remove_edit(self) -> None:
        # Configure auto_sync_targets to include cursor
        write(
            self.workspace / ".agents" / "dotagents-settings.json",
            json.dumps({"auto_sync_targets": ["cursor"]}),
        )
        write(
            self.workspace / ".agents" / "mcp.json",
            json.dumps({"mcpServers": {}}),
        )

        # Add mcp-server triggers auto-sync to cursor
        add_result = self.run_cli("--workspace", "add", "mcp-server", "test-server", "--command", "npx", "--args", "test-arg")
        self.assertIn("Added mcp-server", add_result.human_text)
        self.assertIn("Auto-synced cursor", add_result.human_text)

        # Verify cursor received the new server
        cursor_mcp = json.loads((self.workspace / ".cursor" / "mcp.json").read_text(encoding="utf-8"))
        self.assertIn("test-server", cursor_mcp["mcpServers"])
        self.assertEqual(cursor_mcp["mcpServers"]["test-server"]["command"], "npx")

        # Edit mcp-server triggers auto-sync
        edit_result = self.run_cli("--workspace", "edit", "mcp-server", "test-server", "--command", "node")
        self.assertIn("Edited mcp-server", edit_result.human_text)
        self.assertIn("Auto-synced cursor", edit_result.human_text)

        # Verify cursor has the updated config
        cursor_mcp = json.loads((self.workspace / ".cursor" / "mcp.json").read_text(encoding="utf-8"))
        self.assertEqual(cursor_mcp["mcpServers"]["test-server"]["command"], "node")

        # Remove mcp-server triggers auto-sync
        remove_result = self.run_cli("--workspace", "remove", "mcp-server", "test-server")
        self.assertIn("Removed mcp-server", remove_result.human_text)
        self.assertIn("Auto-synced cursor", remove_result.human_text)

        # Verify cursor no longer has the server
        cursor_mcp = json.loads((self.workspace / ".cursor" / "mcp.json").read_text(encoding="utf-8"))
        self.assertNotIn("test-server", cursor_mcp["mcpServers"])

    def test_add_mcp_server_stdio_transport(self) -> None:
        """Test add mcp-server with stdio transport (command + args)."""
        write(self.workspace / ".agents" / "mcp.json", json.dumps({"mcpServers": {}}))

        result = self.run_cli("--workspace", "add", "mcp-server", "my-server", "--command", "npx", "--args", "run-tool", "--args", "extra-arg")
        self.assertIn("Added mcp-server", result.human_text)

        mcp_config = json.loads((self.workspace / ".agents" / "mcp.json").read_text(encoding="utf-8"))
        self.assertIn("my-server", mcp_config["mcpServers"])
        self.assertEqual(mcp_config["mcpServers"]["my-server"]["command"], "npx")
        self.assertEqual(mcp_config["mcpServers"]["my-server"]["args"], ["run-tool", "extra-arg"])

    def test_add_mcp_server_with_env_vars(self) -> None:
        """Test add mcp-server with environment variables."""
        write(self.workspace / ".agents" / "mcp.json", json.dumps({"mcpServers": {}}))

        result = self.run_cli("--workspace", "add", "mcp-server", "env-server", "--command", "node", "--env", "API_KEY=secret123", "--env", "DEBUG=true")
        self.assertIn("Added mcp-server", result.human_text)

        mcp_config = json.loads((self.workspace / ".agents" / "mcp.json").read_text(encoding="utf-8"))
        self.assertEqual(mcp_config["mcpServers"]["env-server"]["command"], "node")
        self.assertEqual(mcp_config["mcpServers"]["env-server"]["env"]["API_KEY"], "secret123")
        self.assertEqual(mcp_config["mcpServers"]["env-server"]["env"]["DEBUG"], "true")

    def test_add_mcp_server_url_transport(self) -> None:
        """Test add mcp-server with URL transport."""
        write(self.workspace / ".agents" / "mcp.json", json.dumps({"mcpServers": {}}))

        result = self.run_cli("--workspace", "add", "mcp-server", "remote-server", "--url", "https://mcp.example.com/api")
        self.assertIn("Added mcp-server", result.human_text)

        mcp_config = json.loads((self.workspace / ".agents" / "mcp.json").read_text(encoding="utf-8"))
        self.assertIn("remote-server", mcp_config["mcpServers"])
        self.assertEqual(mcp_config["mcpServers"]["remote-server"]["url"], "https://mcp.example.com/api")
        self.assertNotIn("command", mcp_config["mcpServers"]["remote-server"])

    def test_add_mcp_server_duplicate_fails(self) -> None:
        """Test that adding a duplicate MCP server fails."""
        write(self.workspace / ".agents" / "mcp.json", json.dumps({"mcpServers": {"existing": {"command": "old"}}}))

        with self.assertRaises(Exception) as cm:
            self.run_cli("--workspace", "add", "mcp-server", "existing", "--command", "new")
        self.assertIn("already exists", str(cm.exception))

    def test_remove_mcp_server_existing(self) -> None:
        """Test remove mcp-server for an existing server."""
        write(self.workspace / ".agents" / "mcp.json", json.dumps({"mcpServers": {"to-remove": {"command": "npx", "args": ["tool"]}}}))

        result = self.run_cli("--workspace", "remove", "mcp-server", "to-remove")
        self.assertIn("Removed mcp-server", result.human_text)

        mcp_config = json.loads((self.workspace / ".agents" / "mcp.json").read_text(encoding="utf-8"))
        self.assertNotIn("to-remove", mcp_config["mcpServers"])

    def test_remove_mcp_server_nonexistent_fails(self) -> None:
        """Test that removing a non-existent MCP server fails."""
        write(self.workspace / ".agents" / "mcp.json", json.dumps({"mcpServers": {}}))

        with self.assertRaises(Exception) as cm:
            self.run_cli("--workspace", "remove", "mcp-server", "nonexistent")
        self.assertIn("Unknown mcp-server", str(cm.exception))

    def test_remove_mcp_server_clears_disabled_list(self) -> None:
        """Test that removing an MCP server also removes it from disabled list."""
        write(self.workspace / ".agents" / "mcp.json", json.dumps({
            "mcpServers": {"disabled-server": {"command": "node"}},
            "mcpRuntimeDisabledServers": ["disabled-server"]
        }))

        self.run_cli("--workspace", "remove", "mcp-server", "disabled-server")

        mcp_config = json.loads((self.workspace / ".agents" / "mcp.json").read_text(encoding="utf-8"))
        self.assertNotIn("disabled-server", mcp_config["mcpServers"])
        self.assertNotIn("disabled-server", mcp_config.get("mcpRuntimeDisabledServers", []))

    def test_edit_mcp_server_change_command(self) -> None:
        """Test edit mcp-server to change command."""
        write(self.workspace / ".agents" / "mcp.json", json.dumps({"mcpServers": {"my-server": {"command": "npx", "args": ["old-tool"]}}}))

        result = self.run_cli("--workspace", "edit", "mcp-server", "my-server", "--command", "node")
        self.assertIn("Edited mcp-server", result.human_text)

        mcp_config = json.loads((self.workspace / ".agents" / "mcp.json").read_text(encoding="utf-8"))
        self.assertEqual(mcp_config["mcpServers"]["my-server"]["command"], "node")

    def test_edit_mcp_server_add_env_vars(self) -> None:
        """Test edit mcp-server to add environment variables."""
        write(self.workspace / ".agents" / "mcp.json", json.dumps({"mcpServers": {"my-server": {"command": "node"}}}))

        result = self.run_cli("--workspace", "edit", "mcp-server", "my-server", "--env", "NEW_VAR=value1", "--env", "ANOTHER=value2")
        self.assertIn("Edited mcp-server", result.human_text)

        mcp_config = json.loads((self.workspace / ".agents" / "mcp.json").read_text(encoding="utf-8"))
        self.assertEqual(mcp_config["mcpServers"]["my-server"]["env"]["NEW_VAR"], "value1")
        self.assertEqual(mcp_config["mcpServers"]["my-server"]["env"]["ANOTHER"], "value2")

    def test_edit_mcp_server_switch_to_url(self) -> None:
        """Test edit mcp-server to switch from command to URL transport."""
        write(self.workspace / ".agents" / "mcp.json", json.dumps({"mcpServers": {"my-server": {"command": "node", "args": ["tool"]}}}))

        result = self.run_cli("--workspace", "edit", "mcp-server", "my-server", "--url", "https://new-url.com/api")
        self.assertIn("Edited mcp-server", result.human_text)

        mcp_config = json.loads((self.workspace / ".agents" / "mcp.json").read_text(encoding="utf-8"))
        self.assertEqual(mcp_config["mcpServers"]["my-server"]["url"], "https://new-url.com/api")
        # Command-based fields should be cleared when switching to URL
        self.assertNotIn("command", mcp_config["mcpServers"]["my-server"])

    def test_edit_mcp_server_nonexistent_fails(self) -> None:
        """Test that editing a non-existent MCP server fails."""
        write(self.workspace / ".agents" / "mcp.json", json.dumps({"mcpServers": {}}))

        with self.assertRaises(Exception) as cm:
            self.run_cli("--workspace", "edit", "mcp-server", "nonexistent", "--command", "new")
        self.assertIn("Unknown mcp-server", str(cm.exception))

    def test_show_mcp_server_details(self) -> None:
        """Test show mcp-server displays server details."""
        write(self.workspace / ".agents" / "mcp.json", json.dumps({
            "mcpServers": {"detailed-server": {"command": "npx", "args": ["-y", "tool"], "env": {"KEY": "value"}}},
            "mcpRuntimeDisabledServers": []
        }))

        result = self.run_cli("show", "mcp-server", "detailed-server")
        self.assertIn("MCP Server: detailed-server", result.human_text)
        self.assertIn("Enabled: True", result.human_text)
        self.assertIn("npx", result.human_text)

    def test_show_mcp_server_disabled(self) -> None:
        """Test show mcp-server indicates disabled status."""
        write(self.workspace / ".agents" / "mcp.json", json.dumps({
            "mcpServers": {"disabled-server": {"command": "node"}},
            "mcpRuntimeDisabledServers": ["disabled-server"]
        }))

        result = self.run_cli("show", "mcp-server", "disabled-server")
        self.assertIn("MCP Server: disabled-server", result.human_text)
        self.assertIn("Enabled: False", result.human_text)

    def test_show_mcp_server_nonexistent_fails(self) -> None:
        """Test that show mcp-server fails for non-existent server."""
        write(self.workspace / ".agents" / "mcp.json", json.dumps({"mcpServers": {}}))

        with self.assertRaises(Exception) as cm:
            self.run_cli("show", "mcp-server", "nonexistent")
        self.assertIn("Unknown mcp-server", str(cm.exception))

    def test_list_mcp_servers_from_harness_native_configs(self) -> None:
        """Test list mcp-servers shows servers from harness native configs."""
        # Setup .agents mcp.json
        write(self.workspace / ".agents" / "mcp.json", json.dumps({"mcpServers": {"dotagents-server": {"command": "node"}}}))
        # Setup cursor native config
        write(self.workspace / ".cursor" / "mcp.json", json.dumps({"mcpServers": {"cursor-server": {"command": "npx", "args": ["cursor-tool"]}}}))
        # Setup claude-code native config
        write(self.workspace / "claude.json", json.dumps({"mcpServers": {"claude-server": {"url": "https://claude.example.com"}}}))

        result = self.run_cli("list", "mcp-servers")
        self.assertIn("dotagents-server", result.human_text)
        self.assertIn("cursor-server", result.human_text)
        self.assertIn("claude-server", result.human_text)

        # Check payload includes source information
        payload = result.payload
        items = payload["items"]
        sources = {item["id"]: item.get("source") for item in items}
        self.assertEqual(sources.get("dotagents-server"), ".agents")
        self.assertEqual(sources.get("cursor-server"), "cursor")
        self.assertEqual(sources.get("claude-server"), "claude-code")

    def test_dry_run_add_mcp_server(self) -> None:
        """Test --dry-run for add mcp-server does not write."""
        write(self.workspace / ".agents" / "mcp.json", json.dumps({"mcpServers": {}}))

        result = self.run_cli("--workspace", "--dry-run", "add", "mcp-server", "dry-server", "--command", "node")
        self.assertIn("Added mcp-server", result.human_text)

        # Verify file was NOT modified
        mcp_config = json.loads((self.workspace / ".agents" / "mcp.json").read_text(encoding="utf-8"))
        self.assertNotIn("dry-server", mcp_config["mcpServers"])

    def test_dry_run_remove_mcp_server(self) -> None:
        """Test --dry-run for remove mcp-server does not write."""
        write(self.workspace / ".agents" / "mcp.json", json.dumps({"mcpServers": {"existing": {"command": "node"}}}))

        result = self.run_cli("--workspace", "--dry-run", "remove", "mcp-server", "existing")
        self.assertIn("Removed mcp-server", result.human_text)

        # Verify file was NOT modified
        mcp_config = json.loads((self.workspace / ".agents" / "mcp.json").read_text(encoding="utf-8"))
        self.assertIn("existing", mcp_config["mcpServers"])

    def test_dry_run_edit_mcp_server(self) -> None:
        """Test --dry-run for edit mcp-server does not write."""
        write(self.workspace / ".agents" / "mcp.json", json.dumps({"mcpServers": {"existing": {"command": "old"}}}))

        result = self.run_cli("--workspace", "--dry-run", "edit", "mcp-server", "existing", "--command", "new")
        self.assertIn("Edited mcp-server", result.human_text)

        # Verify file was NOT modified
        mcp_config = json.loads((self.workspace / ".agents" / "mcp.json").read_text(encoding="utf-8"))
        self.assertEqual(mcp_config["mcpServers"]["existing"]["command"], "old")

    def test_adapter_list_mcp_servers_reads_native_config(self) -> None:
        """Test adapter list_mcp_servers reads from native harness configs."""
        from dotagents_management_cli.cli import CursorAdapter, ClaudeCodeAdapter, build_context

        # Setup cursor native config
        write(self.workspace / ".cursor" / "mcp.json", json.dumps({
            "mcpServers": {
                "cursor-native": {"command": "npx", "args": ["cursor-tool"]}
            }
        }))

        ctx = build_context(cwd=self.workspace, env=self.env)
        cursor_adapter = CursorAdapter()
        servers = cursor_adapter.list_mcp_servers(ctx, "workspace")

        self.assertEqual(len(servers), 1)
        self.assertEqual(servers[0]["id"], "cursor-native")
        self.assertEqual(servers[0]["source"], "cursor")
        self.assertEqual(servers[0]["config"]["command"], "npx")

    def test_adapter_add_mcp_server_writes_native_config(self) -> None:
        """Test adapter add_mcp_server writes to native harness config."""
        from dotagents_management_cli.cli import CursorAdapter, build_context

        cursor_dir = self.workspace / ".cursor"
        cursor_dir.mkdir(parents=True, exist_ok=True)

        ctx = build_context(cwd=self.workspace, env=self.env)
        cursor_adapter = CursorAdapter()
        result = cursor_adapter.add_mcp_server(ctx, "new-server", {"command": "node", "args": ["tool"]})

        self.assertEqual(result["action"], "add")
        self.assertEqual(result["target"], "cursor")
        self.assertEqual(result["id"], "new-server")

        # Verify native config was written
        cursor_mcp = json.loads((cursor_dir / "mcp.json").read_text(encoding="utf-8"))
        self.assertIn("new-server", cursor_mcp["mcpServers"])
        self.assertEqual(cursor_mcp["mcpServers"]["new-server"]["command"], "node")

    def test_adapter_remove_mcp_server_writes_native_config(self) -> None:
        """Test adapter remove_mcp_server writes to native harness config."""
        from dotagents_management_cli.cli import CursorAdapter, build_context

        # Setup cursor native config with existing server
        write(self.workspace / ".cursor" / "mcp.json", json.dumps({
            "mcpServers": {"to-remove": {"command": "old"}}
        }))

        ctx = build_context(cwd=self.workspace, env=self.env)
        cursor_adapter = CursorAdapter()
        result = cursor_adapter.remove_mcp_server(ctx, "to-remove")

        self.assertEqual(result["action"], "remove")
        self.assertEqual(result["target"], "cursor")
        self.assertEqual(result["id"], "to-remove")

        # Verify native config was updated
        cursor_mcp = json.loads((self.workspace / ".cursor" / "mcp.json").read_text(encoding="utf-8"))
        self.assertNotIn("to-remove", cursor_mcp["mcpServers"])

    def test_adapter_edit_mcp_server_writes_native_config(self) -> None:
        """Test adapter edit_mcp_server writes to native harness config."""
        from dotagents_management_cli.cli import CursorAdapter, build_context

        # Setup cursor native config with existing server
        write(self.workspace / ".cursor" / "mcp.json", json.dumps({
            "mcpServers": {"to-edit": {"command": "old", "args": ["old-arg"]}}
        }))

        ctx = build_context(cwd=self.workspace, env=self.env)
        cursor_adapter = CursorAdapter()
        result = cursor_adapter.edit_mcp_server(ctx, "to-edit", {"command": "new", "args": ["new-arg"]})

        self.assertEqual(result["action"], "edit")
        self.assertEqual(result["target"], "cursor")
        self.assertEqual(result["old_config"]["command"], "old")
        self.assertEqual(result["new_config"]["command"], "new")

        # Verify native config was updated
        cursor_mcp = json.loads((self.workspace / ".cursor" / "mcp.json").read_text(encoding="utf-8"))
        self.assertEqual(cursor_mcp["mcpServers"]["to-edit"]["command"], "new")
        self.assertEqual(cursor_mcp["mcpServers"]["to-edit"]["args"], ["new-arg"])

    def test_adapter_claude_code_list_mcp_servers(self) -> None:
        """Test ClaudeCodeAdapter list_mcp_servers reads from claude.json."""
        from dotagents_management_cli.cli import ClaudeCodeAdapter, build_context

        # Setup claude.json
        write(self.workspace / "claude.json", json.dumps({
            "mcpServers": {
                "claude-mcp": {"url": "https://mcp.example.com"}
            }
        }))

        ctx = build_context(cwd=self.workspace, env=self.env)
        adapter = ClaudeCodeAdapter()
        servers = adapter.list_mcp_servers(ctx, "workspace")

        self.assertEqual(len(servers), 1)
        self.assertEqual(servers[0]["id"], "claude-mcp")
        self.assertEqual(servers[0]["source"], "claude-code")
        self.assertEqual(servers[0]["config"]["url"], "https://mcp.example.com")

    def test_adapter_claude_code_add_remove_edit(self) -> None:
        """Test ClaudeCodeAdapter add/remove/edit mcp-server."""
        from dotagents_management_cli.cli import ClaudeCodeAdapter, build_context

        ctx = build_context(cwd=self.workspace, env=self.env)
        adapter = ClaudeCodeAdapter()

        # Add
        add_result = adapter.add_mcp_server(ctx, "claude-new", {"command": "node"})
        self.assertEqual(add_result["target"], "claude-code")
        claude_config = json.loads((self.workspace / "claude.json").read_text(encoding="utf-8"))
        self.assertIn("claude-new", claude_config["mcpServers"])

        # Edit
        edit_result = adapter.edit_mcp_server(ctx, "claude-new", {"command": "npx"})
        self.assertEqual(edit_result["new_config"]["command"], "npx")
        claude_config = json.loads((self.workspace / "claude.json").read_text(encoding="utf-8"))
        self.assertEqual(claude_config["mcpServers"]["claude-new"]["command"], "npx")

        # Remove
        remove_result = adapter.remove_mcp_server(ctx, "claude-new")
        self.assertEqual(remove_result["action"], "remove")
        claude_config = json.loads((self.workspace / "claude.json").read_text(encoding="utf-8"))
        self.assertNotIn("claude-new", claude_config["mcpServers"])

    def test_auto_sync_disabled_for_dry_run(self) -> None:
        """Test that auto-sync does not trigger during dry-run."""
        write(self.workspace / ".agents" / "dotagents-settings.json", json.dumps({"auto_sync_targets": ["cursor"]}))
        write(self.workspace / ".agents" / "mcp.json", json.dumps({"mcpServers": {}}))

        result = self.run_cli("--workspace", "--dry-run", "add", "mcp-server", "test-server", "--command", "node")
        self.assertIn("Added mcp-server", result.human_text)
        # Auto-sync should NOT be mentioned
        self.assertNotIn("Auto-synced", result.human_text)

        # Verify cursor was NOT updated
        self.assertFalse((self.workspace / ".cursor" / "mcp.json").exists())


if __name__ == "__main__":
    unittest.main()