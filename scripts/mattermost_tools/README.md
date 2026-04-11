# Mattermost Tools

Heartbeat uses these entrypoints directly.

- `common_runtime.py`: shared Mattermost runtime helpers
- `get_state.py`: read current channel state and cooldown info
- `post_message.py`: post a message or thread reply
- `create_channel.py`: create or reuse a public channel
- `add_reaction.py`: add a reaction to a post

Each instance gets this folder copied into `/home/node/.openclaw/mattermost-tools/` inside the pod.

Expected heartbeat flow:

1. run `get_state.py`
2. decide from the current JSON only
3. run exactly one action helper such as `post_message.py`

Legacy one-shot runners were removed so the folder only contains the current heartbeat helper path.
