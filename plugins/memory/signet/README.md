# Signet Memory Provider

[Signet](https://github.com/Signet-AI/signetai) is a portable context layer for
AI agents. It keeps durable memory outside any one harness so Hermes can share
the same long-lived record as other tools without embedding Signet's storage
engine inside the Hermes process.

The record stays inspectable: Signet keeps readable workspace files such as
`MEMORY.md` and stores operational memory in SQLite at
`$SIGNET_WORKSPACE/memory/memories.db`. SQLite is the query, indexing, audit,
and mutation layer over that durable memory state. Signet can also structure
extracted entities and relations into a navigable graph, but the graph and
retrieval internals are support layers for context selection, not the product
by themselves.

This provider is the Hermes bridge. It calls the local Signet daemon during
Hermes session lifecycle events and exposes Signet's memory tools to Hermes
when explicit recall or memory repair is needed.

## Requirements

- Signet daemon running on localhost:3850 by default
- Install Signet with `npm install -g signetai` or `bun add -g signetai`

## Setup

```bash
hermes memory setup    # select "signet"
```

Or manually:

```bash
hermes config set memory.provider signet
signet daemon start
```

## Config

`hermes memory setup` saves `daemon_url` and `agent_id` to
`$HERMES_HOME/signet.json`. Environment variables override that file at
runtime.

Environment variables:

- `SIGNET_DAEMON_URL` - Full daemon URL (default: `http://localhost:3850`)
- `SIGNET_HOST` / `SIGNET_PORT` - Host and port separately
- `SIGNET_AGENT_ID` - Agent scope identifier (default: `hermes-agent`)
- `SIGNET_AGENT_WORKSPACE` - Optional named-agent workspace path
- `SIGNET_AGENT_READ_POLICY` - Optional named-agent memory policy for first registration: `shared`, `isolated`, or `group`
- `SIGNET_AGENT_POLICY_GROUP` - Required when `SIGNET_AGENT_READ_POLICY=group`

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
`importance`, `tags`, `pinned`, `project`, recall hints, source transcript
text, and pre-structured entity/aspect data.

## Session Lifecycle

The provider maps Hermes lifecycle events onto Signet daemon hooks:

1. **Session start** - Opens a Signet session and asks the daemon for the
   initial memory block Hermes should make available to the model.
2. **User prompt submit** - Sends the latest user message to Signet before the
   next model step so Signet can return relevant context from the durable
   record.
3. **Turn sync** - Accumulates the assistant side of the exchange so the
   session transcript is complete.
4. **Pre-compression** - Asks Signet for guidance before Hermes summarizes or
   compacts a long context.
5. **Compaction complete** - Sends the completed summary back to Signet as a
   first-class session artifact.
6. **Session end** - Sends the cleaned conversation transcript to Signet so the
   daemon can queue durable memory processing.
7. **Delegation** - Records useful delegated-task outcomes through Signet.

All heavy storage and processing stays in the Signet daemon. Hermes only needs
this provider, stdlib HTTP calls, and a configured daemon URL.
