import io
import json
import unittest

from app.mcp import dispatch, serve_stdio


class MCPTests(unittest.TestCase):
    def test_initialize_and_tools_list(self):
        initialized = dispatch({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        self.assertEqual(initialized["result"]["protocolVersion"], "2025-06-18")
        listed = dispatch({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        self.assertEqual({item["name"] for item in listed["result"]["tools"]}, {"harness_run", "harness_tools", "harness_replay"})

    def test_stdio_round_trip_and_replay_tool(self):
        request = "\n".join([
            json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}),
            json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}),
            json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "harness_tools", "arguments": {}}}),
        ]) + "\n"
        output = io.StringIO()
        self.assertEqual(serve_stdio(io.StringIO(request), output), 0)
        responses = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual(len(responses), 2)
        self.assertFalse(responses[1]["result"]["isError"])
        self.assertTrue(responses[1]["result"]["structuredContent"]["tools"])

    def test_high_risk_action_is_not_promoted_to_success(self):
        response = dispatch({
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "harness_run", "arguments": {"task_id": "delete", "prompt": "delete", "tool": "delete_file", "arguments": {"path": "temporary.txt"}, "initial_files": {"temporary.txt": "secret"}}},
        })
        self.assertFalse(response["result"]["structuredContent"]["verified_success"])

