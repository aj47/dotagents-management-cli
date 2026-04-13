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


if __name__ == "__main__":
    unittest.main()