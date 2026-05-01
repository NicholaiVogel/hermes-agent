# Signet Memory Provider

[Signet](https://github.com/Signet-AI/signetai) is a portable context layer for
AI agents. It gives Hermes a durable memory record that follows the user across
tools instead of living only inside one provider, one profile, or one runtime.

This provider is the Hermes bridge. Hermes sends conversation lifecycle events
to the local Signet daemon, and Signet handles persistence, audit history,
structured context, cognitive behavioral modeling, summaries, and recall
outside the Hermes process.

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

The setup wizard checks the daemon, saves Hermes-local Signet settings, and
registers the configured Hermes profile with Signet when possible.

## How It Differs

The other bundled Hermes memory provider READMEs generally describe how Hermes
talks to a provider-specific SDK, API, CLI, daemon, or local store. Signet's
distinction is the boundary it creates: Hermes gets a small integration surface,
while Signet owns the durable context substrate and can serve the same record to
other harnesses.

That makes the integration useful in a few practical ways:

- **Portable** - memory is not trapped in a single Hermes profile or runtime.
- **Inspectable** - the workspace includes readable files such as `MEMORY.md`,
  plus SQLite at `$SIGNET_WORKSPACE/memory/memories.db`.
- **Auditable** - SQLite is the query, indexing, audit, and mutation layer over
  durable memory state.
- **Cognitive behavioral modeling** - user understanding emerges from
  accumulated memories, preferences, decisions, entities, and relationships
  instead of a separate profile-management layer.
- **Fine-grained recall** - Hermes gets simple flat hybrid recall tools, while
  Signet also keeps navigable and tunable recall surfaces for more specific
  searches through memory structure.
- **Lifecycle-aware** - Signet receives session start, prompt, turn, compaction,
  delegation, and session-end events, not just isolated search/store calls.
- **Runtime-light** - heavy storage and processing stay in the Signet daemon, so
  Hermes does not need to embed Signet's memory engine.

Signet can also organize extracted entities and relationships into a navigable
graph, but the graph and retrieval internals exist to support context selection
rather than acting as the product by themselves. Cognitive behavioral modeling
and fine-grained recall are byproducts of that structure: the daemon can reason
over what has been remembered and how it relates, without forcing Hermes to
manage a parallel representation system.

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
| `SIGNET_AGENT_READ_POLICY` | Optional named-agent memory policy: `shared`, `isolated`, or `group` |
| `SIGNET_AGENT_POLICY_GROUP` | Required when `SIGNET_AGENT_READ_POLICY=group` |

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
`importance`, `tags`, `pinned`, `project`, recall hints, source transcript text,
and pre-structured entity/aspect data.

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
