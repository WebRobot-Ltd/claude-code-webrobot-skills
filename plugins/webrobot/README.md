# WebRobot for Claude Code

Drive the [WebRobot](https://webrobot.eu) data and agent platform from Claude Code: build and run
data pipelines (web, files, databases, open-data APIs) on Spark or Scrapy, on the shared cluster or
on ephemeral VMs; query the datasets they produce; design, run and schedule Agent Studio agents and
teams; publish vertical apps; and work with knowledge bases and analytics reports.

## Install

```
/plugin marketplace add WebRobot-Ltd/claude-code-webrobot-skills
/plugin install webrobot@webrobot
```

Claude Code asks for your **WebRobot API key** when the plugin is enabled. Create one in the
WebRobot console under **Developer → API → Request New API Key** and paste it as `key_id:secret`.
The key is stored as a secret and sent only to the WebRobot MCP server
(`https://mcp-full.webrobot.eu/mcp`). Everything it does stays inside the key's organization and
is limited by its role.

Check the connection with `/mcp` (the `webrobot` server should be connected), then ask Claude
"who am I on WebRobot?" — the `webrobot-setup` skill verifies the key and your organization.

## Skills

| Skill | Use it for |
|---|---|
| `webrobot-setup` | Connecting, checking the key, finding the right tool for a task |
| `webrobot-overview` | What the platform does and how its parts fit together |
| `webrobot-pipeline` | Writing, validating and running pipelines (stages, selectors, multi-source match) |
| `webrobot-datasets` | Uploading, querying and exporting datasets |
| `webrobot-agents` | Agent Studio agents and teams, background runs, schedules |
| `webrobot-app-builder` | Vertical apps from a description to a live app |
| `webrobot-admin` | Organizations, users, keys, plans (admins) |
| `webrobot-cli` | The WebRobot command-line tool |
| `webrobot-plugin-dev`, `webrobot-frontend-plugin-dev`, `webrobot-python-extension` | Extending the platform |
| `webrobot-sdk-python`, `webrobot-sdk-nodejs`, `webrobot-sdk-java` | Calling the API from your own code |

## Data handling

The plugin has no code of its own: it is a set of skills and the address of the hosted WebRobot
MCP server. Requests go to WebRobot with your key; the data stays in your WebRobot organization.

## License

MIT — see the repository's README. Source: https://github.com/WebRobot-Ltd/claude-code-webrobot-skills
