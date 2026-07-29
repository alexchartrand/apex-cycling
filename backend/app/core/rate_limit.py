from slowapi import Limiter
from slowapi.util import get_remote_address

# In-memory, per-process limiter. Note: prod runs multiple uvicorn workers,
# so the effective limit per client is roughly (configured limit * worker
# count) since each worker keeps its own counters. Acceptable for now given
# no shared store (e.g. Redis) exists in this stack; revisit if that changes.
limiter = Limiter(key_func=get_remote_address, default_limits=[])
