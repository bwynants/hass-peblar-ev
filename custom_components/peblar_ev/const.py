"""Constants for the Peblar EV (Modbus) integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "peblar_ev"

# Config entry keys (connection)
CONF_HOST = "host"
CONF_PORT = "port"
CONF_FRAMER = "framer"
CONF_UNIT_ID = "unit_id"

FRAMER_SOCKET = "socket"
FRAMER_RTU = "rtu"

# Options keys (tunables) + defaults
CONF_MAX_CURRENT = "max_current"  # A (22 kW = 32, 11 kW = 16)
CONF_HEARTBEAT = "heartbeat_seconds"
CONF_ALIVE_TIMEOUT = "alive_timeout_seconds"
CONF_FALLBACK_CURRENT = "fallback_current_a"
CONF_PAUSE_LIMIT = "pause_limit_per_10min"

DEFAULT_PORT = 502
DEFAULT_FRAMER = FRAMER_SOCKET
DEFAULT_UNIT_ID = 1
DEFAULT_MAX_CURRENT = 32.0
DEFAULT_MIN_CURRENT = 6.0
DEFAULT_HEARTBEAT = 30
DEFAULT_ALIVE_TIMEOUT = 60
DEFAULT_FALLBACK_CURRENT = 0.0
DEFAULT_PAUSE_LIMIT = 3

# Polling
UPDATE_INTERVAL = timedelta(seconds=10)

# Policy timing
SYNC_OFF_DEBOUNCE = timedelta(seconds=5)  # actual==0 must persist this long
WRITE_DEBOUNCE_SECONDS = 2.0
PAUSE_WINDOW = timedelta(minutes=10)  # rolling window for the relay-protection guard

# How long the link must stay down before the connectivity sensor reports a
# problem. Mirrors the 2-minute delay_on of the YAML setup this replaces: a
# short flap self-heals and should not raise an alarm.
LINK_DOWN_GRACE = timedelta(minutes=2)
