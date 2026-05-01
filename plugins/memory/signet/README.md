# Signet Memory Provider

[Signet](https://github.com/Signet-AI/signetai) is a portable context layer for
AI agents. It gives Hermes access to a workspace-backed memory record that can
travel across tools, sessions, and runtimes.

This provider sends Hermes conversation lifecycle events to the local Signet
daemon. Signet handles persistence, audit history, structured context,
cognitive behavioral modeling, summaries, and recall outside the Hermes
process.

## Requirements

- Signet installed with `npm install -g signetai` or `bun add -g signetai`
- Signet daemon running on `http://localhost:3850` by default

```bash
signet daemon start
```

## Setup

```bash
hermes memory setup    # select "signet"
```

Or manually:

```bash
hermes config set memory.provider signet
signet daemon start
```

The setup wizard checks the daemon and saves Hermes-local Signet settings.

## Why Signet

Signet is built around an agent workspace rather than a plugin-local memory
bucket. The workspace keeps the durable record; the daemon indexes, searches,
summarizes, and structures it. Hermes gets a small integration surface while
Signet owns the memory system around it.

The important boundary is that the workspace stays durable and inspectable
while SQLite, search indexes, graph structure, summaries, and recall surfaces
remain service layers around it. Hermes can use the memory system without
taking responsibility for that substrate.

What Signet adds:

- **Portable workspace memory** - memory can follow the user between Hermes and
  other harnesses instead of being trapped in one runtime profile.
- **Readable source record** - the workspace includes files such as `MEMORY.md`;
  SQLite at `$SIGNET_WORKSPACE/memory/memories.db` provides the query, indexing,
  audit, and mutation layer around that durable state.
- **Cognitive behavioral modeling** - user understanding emerges from
  accumulated memories, preferences, decisions, entities, relationships, and
  session artifacts instead of a separate profile-management layer.
- **Fine-grained recall** - Hermes gets flat hybrid recall tools for simple
  use, while Signet also keeps navigable and tunable recall surfaces for more
  specific searches through memory structure.
- **Lifecycle-aware ingestion** - Signet receives session start, prompt, turn,
  compaction, delegation, and session-end events, so it can work from the shape
  of the conversation rather than only isolated search/store calls.
- **Runtime-light integration** - heavy storage and processing stay in the
  Signet daemon, so Hermes does not need to embed Signet's memory engine.

## Config

Config file: `$HERMES_HOME/signet.json`

| Key | Default | Description |
|-----|---------|-------------|
| `daemon_url` | `http://localhost:3850` | Signet daemon base URL |
| `agent_id` | `hermes-agent` | Signet agent scope used for Hermes memory |

Environment variables override the config file:

| Env Var | Description |
|---------|-------------|
| `SIGNET_DAEMON_URL` | Full daemon URL |
| `SIGNET_HOST` / `SIGNET_PORT` | Host and port separately |
| `SIGNET_AGENT_ID` | Agent scope identifier |
| `SIGNET_AGENT_WORKSPACE` | Optional named-agent workspace path for first registration |

## Tools

| Tool | Description |
|------|-------------|
| `memory_search` | Search Signet's durable memory record |
| `memory_store` | Save a memory through the Signet daemon |
| `memory_get` | Retrieve a memory by ID |
| `memory_list` | List memories with optional filters |
| `memory_modify` | Edit an existing memory with audit history |
| `memory_forget` | Soft-delete a memory with a reason |
| `recall` / `remember` | Compatibility aliases for search/store |

`memory_store` accepts plain content plus optional metadata such as `type`,
`importance`, `tags`, `pinned`, recall hints, source transcript text, and
pre-structured entity/aspect data.

## Session Lifecycle

When enabled, Hermes calls this provider at key points in a conversation:

| Event | What the provider sends to Signet |
|-------|-----------------------------------|
| Session start | Opens a Signet session and asks for the initial memory block Hermes should make available |
| User prompt submit | Sends the latest user message before the next model step so Signet can return relevant context |
| Turn sync | Adds the assistant response to the in-progress transcript |
| Pre-compression | Asks Signet what should be preserved before Hermes compacts a long context |
| Compaction complete | Sends the completed summary back as a session artifact |
| Session end | Sends the cleaned transcript so Signet can queue durable memory processing |
| Delegation | Records useful delegated-task outcomes through Signet |

Heavy processing stays in the Signet daemon. The Hermes plugin uses stdlib HTTP
calls and keeps background writes bounded so session shutdown can drain pending
work before the process exits.
