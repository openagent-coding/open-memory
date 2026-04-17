# Architecture

## System Overview

```mermaid
graph TB
    subgraph Agents
        CC[Claude Code]
        CU[Cursor]
        OA[Other MCP Agents]
    end

    subgraph "Open Memory Server"
        MCP[FastMCP Server<br/>stdio / streamable-http]
        TOOLS[6 MCP Tools<br/>save · get · search<br/>delete · consolidate · stats]
        SVC[Memory Service<br/>dedup · RRF search · caps]
        EMB[Embedding Manager<br/>dual models: text + code<br/>single model opt-in]
        CLN[Cleanup Service<br/>TTL · eviction]
    end

    subgraph Storage
        PG[(PostgreSQL + pgvector<br/>single memories table)]
    end

    CC -->|MCP protocol| MCP
    CU -->|MCP protocol| MCP
    OA -->|MCP protocol| MCP

    MCP --> TOOLS
    TOOLS --> SVC
    SVC --> EMB
    SVC --> PG
    CLN -->|periodic| PG
```

## Database Schema

Single table design with `memory_type` discriminator:

```mermaid
erDiagram
    memories {
        uuid id PK
        varchar memory_type "user_memory | project_memory | project_guidelines | agent_memory"
        varchar entity_key "scoping key (user, project name, agent id)"
        text content
        jsonb metadata
        vector embedding "primary embedding (256d default)"
        vector code_embedding "optional, only in dual-model mode"
        varchar content_type "text | code | mixed"
        timestamptz created_at
        timestamptz updated_at
        timestamptz last_accessed
        integer access_count
    }
```

**Indexes:**
- `(memory_type, entity_key)` — B-tree composite for filtered lookups
- `embedding` — HNSW with `vector_cosine_ops` for semantic search
- `code_embedding` — HNSW (only created when `DUAL_EMBEDDING=true`)
- `last_accessed` — B-tree for cleanup ordering

## Write Flow (Dedup-on-Write)

```mermaid
flowchart TD
    A[Agent calls save_memory] --> B[Embed content with text model<br/>Nomic Embed Text v1.5]
    B --> C{Dual mode + code/mixed content?}
    C -->|Yes| D[Also embed with code model<br/>CodeRankEmbed-137M]
    C -->|No| E[Text embedding only]

    D --> F[Acquire advisory lock<br/>on memory_type + entity_key]
    E --> F

    F --> G[Find similar entries<br/>cosine similarity >= 0.85]
    G --> H{Duplicate found?}

    H -->|Yes, sim >= 0.90| I[Replace content]
    H -->|Yes, sim 0.85-0.90| J[Append to existing]
    H -->|No| K[Insert new row]

    I --> L[Update existing record]
    J --> L
    L --> M[Release lock]
    K --> M

    M --> N[Enforce cap per memory_type + entity_key]
    N --> O{Over cap?}
    O -->|Yes| P[Evict lowest-scored entries<br/>score = access_count / age_days]
    O -->|No| Q[Done]
    P --> Q
```

## Search Flow

```mermaid
flowchart TD
    A[Agent calls search_memory] --> B[Embed query with primary model]
    B --> C{Dual mode?}

    C -->|No| D[Search embedding column<br/>across selected memory_types]
    C -->|Yes| E[Search both columns<br/>in parallel]

    E --> F[Reciprocal Rank Fusion<br/>RRF score = Σ 1/k+rank]
    D --> G[Rank by cosine similarity]
    F --> G

    G --> H[Update access_count<br/>on returned entries]
    H --> I[Return top-k results]
```

## Embedding Architecture

```mermaid
flowchart LR
    subgraph "Default: Dual Model"
        D[Content] --> E[Classifier]
        E -->|all content| F[Text Model<br/>Nomic Embed Text v1.5<br/>256d Matryoshka]
        E -->|code/mixed| G[Code Model<br/>CodeRankEmbed-137M<br/>768d]
        F --> H[embedding column]
        G --> I[code_embedding column]
    end

    subgraph "Opt-in: Single Model (DUAL_EMBEDDING=false)"
        A[Content] --> B[Primary Model<br/>any model<br/>configurable dim]
        B --> C[embedding column]
    end
```

**Why dual model by default:** Coding agent memory is inherently mixed — natural language preferences alongside code patterns. Nomic Embed Text v1.5 excels at text, CodeRankEmbed-137M excels at code. The primary model always embeds everything (so search always works), while the code model adds a second embedding for code-heavy content to improve code-specific retrieval. Combined ~500MB, both run on CPU.

## Cleanup and Eviction

```mermaid
flowchart TD
    subgraph "Background Loop (runs on startup + every 24h)"
        A[For each memory_type] --> B{TTL > 0?}
        B -->|Yes| C[DELETE WHERE memory_type = X<br/>AND created_at + TTL < now]
        B -->|No / permanent| D[Skip]
    end

    subgraph "On Write (per memory_type + entity_key)"
        E[After insert] --> F{Count > cap?}
        F -->|Yes| G[CTE: rank by score DESC<br/>DELETE WHERE rank > cap]
        F -->|No| H[Done]
    end
```

## Deployment

### Docker Compose

```mermaid
graph LR
    subgraph "docker compose up"
        PG[pgvector/pgvector:pg17<br/>Port 5432]
        MS[open-memory server<br/>Port 8080]
    end

    MS -->|asyncpg pool| PG
    AGENT[Agent] -->|MCP over HTTP| MS
```

### Kubernetes

```mermaid
graph TB
    subgraph "Kubernetes Cluster"
        CM[ConfigMap] --> MS[Open Memory Pod]
        SC[Secret] --> MS
        SC --> PG[PostgreSQL Pod]
        MS -->|asyncpg| PGS[postgres:5432]
        PG --> PGS
        MS --> MSS[open-memory:8080]
        PG -.-> PVC1[postgres-data 10Gi]
        MS -.-> PVC2[model-cache 5Gi]
    end

    AGENT[Agent] -->|MCP over HTTP| MSS
```

## Configurable Models

| Variable | Default | Purpose |
|----------|---------|---------|
| `EMBEDDING_MODEL` | `nomic-ai/nomic-embed-text-v1.5` | HuggingFace model for text embeddings |
| `EMBEDDING_DIM` | `256` | Output dimension (Matryoshka truncation) |
| `DUAL_EMBEDDING` | `true` | Dual text+code model mode (disable for single model) |
| `CODE_EMBEDDING_MODEL` | `nomic-ai/CodeRankEmbed` | Code model (only when dual=true) |
| `CODE_EMBEDDING_DIM` | `768` | Code embedding dimension |
| `ENABLE_GPU` | `false` | Route inference to CUDA |

> **Note:** Changing the embedding model or dimension after data exists will make existing embeddings incompatible. Re-embed or start fresh.
