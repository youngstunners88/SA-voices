# State Management Skill

Comprehensive state management for voice agent conversations.

## Overview

This skill provides robust state management for SA Voices, handling conversation context, voice profiles, and session persistence.

## Usage

```python
from skills.state_management import ConversationManager, VoiceProfile

# Initialize
manager = ConversationManager()

# Create session
session = await manager.create_session(
    user_id="user123",
    language="zu"
)

# Add messages
await manager.add_message(
    session_id=session.session_id,
    role="user",
    content="Sawubona",
    language="zu"
)

# Get context
context = await manager.get_context_window(session.session_id)
```

## Features

- **Session Management**: Create, update, end sessions
- **Message History**: Store and retrieve conversation messages
- **Voice Profiles**: Persistent voice preferences per user
- **Context Windows**: Get recent messages for LLM context
- **Multi-backend**: Redis, SQLite, or file-based storage
- **TTL Support**: Automatic session expiration

## Storage Backends

### Redis (Production)
```python
from skills.state_management import RedisStorage
storage = RedisStorage("redis://localhost:6379/0")
manager = ConversationManager(storage_backend=storage)
```

### SQLite (Development)
```python
from skills.state_management import SQLiteStorage
storage = SQLiteStorage("./data/state.db")
manager = ConversationManager(storage_backend=storage)
```

### File Storage (Simple)
```python
from skills.state_management import FileStorage
storage = FileStorage("./data/sessions")
manager = ConversationManager(storage_backend=storage)
```

## Configuration

```yaml
state_management:
  session_timeout: 3600  # seconds
  max_messages: 100
  storage_backend: "redis"
  redis_url: "redis://localhost:6379/0"
```
