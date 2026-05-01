# Memory Hygiene

Caps, TTLs, eviction mechanics, and maintenance procedures.

## Capacity Limits

| Memory Type | Cap | TTL | Eviction |
|-------------|-----|-----|----------|
| `user_memory` | 500 entries | Permanent (0 days) | Oldest least-accessed when cap exceeded |
| `project_memory` | 1,000 entries | 90 days | Auto-expired after TTL, then cap eviction |
| `project_guidelines` | 500 entries | Permanent (0 days) | Oldest least-accessed when cap exceeded |
| `agent_memory` | 500 entries | 30 days | Auto-expired after TTL, then cap eviction |

Caps and TTLs are per entity_key. A project with entity_key `"my-app"` has its own
1,000 project_memory slots independent of `"other-app"`.

## TTL Expiration

A background cleanup task runs every 24 hours (configurable via `CLEANUP_INTERVAL_HOURS`).
It deletes entries older than their TTL based on `updated_at` timestamp.

- TTL = 0 means permanent (no auto-expiration)
- `agent_memory` entries expire after 30 days of not being updated
- `project_memory` entries expire after 90 days of not being updated

## Cap Eviction

When `save_memory` inserts a new entry and the cap is exceeded:
1. Entries are scored: `access_count / age_in_days`
2. The lowest-scored entry is evicted to make room

Frequently accessed recent entries survive; old unaccessed entries are evicted first.

## When to Consolidate

Run `consolidate_memories` when:
- `memory_stats` shows a type at >75% of cap (e.g., >375 user_memories)
- After a burst of saves (e.g., onboarding to a new project)
- User explicitly requests cleanup

Consolidation groups entries above the threshold (default 0.80) and merges each cluster
into a single entry. The merged entry keeps the most recent `updated_at` and combined
metadata.

## Consolidation Example

Before: 3 similar entries about testing conventions
```
"Use pytest for all tests"
"Tests should use pytest framework"
"pytest is the standard test framework, fixtures go in conftest.py"
```

After consolidation (threshold 0.80): 1 merged entry
```
"pytest is the standard test framework, fixtures go in conftest.py"
```

## Maintenance Checklist

For periodic maintenance (monthly or when prompted):

1. Run `memory_stats(entity_key=PROJECT_NAME)` for each active project
2. For types above 75% cap: `consolidate_memories(memory_type, entity_key, threshold=0.80)`
3. Review `agent_memory` entries -- delete any that are no longer applicable
4. Check if any `project_memory` entries should be promoted to `project_guidelines`
   (if they describe a convention rather than a point-in-time decision)

## Troubleshooting

**"My memory disappeared"**
- Check TTL: `agent_memory` expires in 30 days, `project_memory` in 90 days
- Check cap eviction: low-access-count entries are evicted first when cap is hit
- Check dedup: if you saved similar content, it may have merged into an existing entry

**"Memory search returns nothing"**
- Check entity_key matches (case-sensitive)
- Lower `min_similarity` to 0.3 for broader matching
- Omit `entity_key` to search across all scopes
- Try rephrasing the query in natural language

## Environment Variables

All caps/TTLs are configurable via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `USER_MEMORY_CAP` | 500 | Max user_memory entries per entity |
| `PROJECT_MEMORY_CAP` | 1000 | Max project_memory entries per entity |
| `PROJECT_GUIDELINES_CAP` | 500 | Max project_guidelines entries per entity |
| `AGENT_MEMORY_CAP` | 500 | Max agent_memory entries per entity |
| `USER_MEMORY_TTL_DAYS` | 0 | Days until user_memory expires (0=permanent) |
| `PROJECT_MEMORY_TTL_DAYS` | 90 | Days until project_memory expires |
| `PROJECT_GUIDELINES_TTL_DAYS` | 0 | Days until project_guidelines expires (0=permanent) |
| `AGENT_MEMORY_TTL_DAYS` | 30 | Days until agent_memory expires |
| `SIMILARITY_THRESHOLD` | 0.85 | Dedup similarity threshold on save |
| `CLEANUP_INTERVAL_HOURS` | 24 | Hours between TTL cleanup runs |
