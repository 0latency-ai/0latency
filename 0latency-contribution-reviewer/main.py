#!/usr/bin/env python3
"""Main entry point for 0Latency Contribution Reviewer."""

import uvicorn

# Load configuration FIRST before importing app modules
from app.config import load_config
config = load_config('config.yaml')

# Now import app after config is loaded
from app.webhook import app


if __name__ == '__main__':
    # Run server
    uvicorn.run(
        app,
        host=config.get('server.host', '0.0.0.0'),
        port=config.get('server.port', 8765),
        log_level='info'
    )
