"""
SafeWatch — shared slowapi Limiter instance.

FIX: main.py and routes.py each need a reference to the *same* Limiter
(slowapi enforces via `request.app.state.limiter`, and `@limiter.limit(...)`
decorators must come from that same instance or the per-route limits are
silently ignored). Centralizing it here avoids the easy mistake of
instantiating two separate Limiter()s.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)