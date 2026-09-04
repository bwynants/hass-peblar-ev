"""Config and options flow for the Peblar EV (Modbus) integration.

The integration owns its Modbus link (see `connection.py`), so the user gives
the charger's address here rather than picking a shared connection. Each entry
is probed before it is created, so a wrong host, port or unit id is reported in
the form instead of failing later at setup.
"""

from __future__ import annotations

from contextlib import suppress
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)
from modbus_connection import ModbusError

from .connection import create_modbus_connection
from .const import (
    CONF_ALIVE_TIMEOUT,
    CONF_FALLBACK_CURRENT,
    CONF_FRAMER,
    CONF_HEARTBEAT,
    CONF_HOST,
    CONF_MAX_CURRENT,
    CONF_PAUSE_LIMIT,
    CONF_PORT,
    CONF_UNIT_ID,
    DEFAULT_ALIVE_TIMEOUT,
    DEFAULT_FALLBACK_CURRENT,
    DEFAULT_FRAMER,
    DEFAULT_HEARTBEAT,
    DEFAULT_MAX_CURRENT,
    DEFAULT_PAUSE_LIMIT,
    DEFAULT_PORT,
    DEFAULT_UNIT_ID,
    DOMAIN,
    FRAMER_RTU,
    FRAMER_SOCKET,
)
from .peblar_modbus import PeblarModbusDevice

_PORT = NumberSelector(
    NumberSelectorConfig(min=1, max=65535, step=1, mode=NumberSelectorMode.BOX)
)
_UNIT = NumberSelector(
    NumberSelectorConfig(min=1, max=247, step=1, mode=NumberSelectorMode.BOX)
)
_FRAMER = SelectSelector(
    SelectSelectorConfig(
        options=[FRAMER_SOCKET, FRAMER_RTU],
        mode=SelectSelectorMode.DROPDOWN,
        translation_key="framer",
    )
)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): TextSelector(),
        vol.Required(CONF_PORT, default=DEFAULT_PORT): _PORT,
        vol.Required(CONF_FRAMER, default=DEFAULT_FRAMER): _FRAMER,
        vol.Required(CONF_UNIT_ID, default=DEFAULT_UNIT_ID): _UNIT,
    }
)


def _options_schema(options: dict[str, Any]) -> vol.Schema:
    """Build the options schema, defaulted to the current values."""
    return vol.Schema(
        {
            vol.Required(
                CONF_MAX_CURRENT,
                default=options.get(CONF_MAX_CURRENT, DEFAULT_MAX_CURRENT),
            ): NumberSelector(
                NumberSelectorConfig(min=6, max=32, step=1, mode=NumberSelectorMode.BOX)
            ),
            vol.Required(
                CONF_HEARTBEAT,
                default=options.get(CONF_HEARTBEAT, DEFAULT_HEARTBEAT),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=5, max=300, step=1, mode=NumberSelectorMode.BOX
                )
            ),
            vol.Required(
                CONF_ALIVE_TIMEOUT,
                default=options.get(CONF_ALIVE_TIMEOUT, DEFAULT_ALIVE_TIMEOUT),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=0, max=3600, step=1, mode=NumberSelectorMode.BOX
                )
            ),
            vol.Required(
                CONF_FALLBACK_CURRENT,
                default=options.get(CONF_FALLBACK_CURRENT, DEFAULT_FALLBACK_CURRENT),
            ): NumberSelector(
                NumberSelectorConfig(min=0, max=32, step=1, mode=NumberSelectorMode.BOX)
            ),
            vol.Required(
                CONF_PAUSE_LIMIT,
                default=options.get(CONF_PAUSE_LIMIT, DEFAULT_PAUSE_LIMIT),
            ): NumberSelector(
                NumberSelectorConfig(min=1, max=10, step=1, mode=NumberSelectorMode.BOX)
            ),
        }
    )


async def _async_probe(data: dict[str, Any]) -> bool:
    """Whether a Peblar charger answers with these connection settings."""
    connection = None
    try:
        connection = create_modbus_connection(data)
        unit = connection.for_unit(int(data[CONF_UNIT_ID]))
        await PeblarModbusDevice.async_probe(unit)
    except (ModbusError, OSError, ValueError):
        return False
    finally:
        if connection is not None:
            with suppress(ModbusError, OSError):
                await connection.close()
    return True


def _connection_data(user_input: dict[str, Any]) -> dict[str, Any]:
    """Normalise the connection fields from a submitted form."""
    return {
        CONF_HOST: str(user_input[CONF_HOST]).strip(),
        CONF_PORT: int(user_input[CONF_PORT]),
        CONF_FRAMER: str(user_input[CONF_FRAMER]),
        CONF_UNIT_ID: int(user_input[CONF_UNIT_ID]),
    }


class PeblarEvConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the initial setup."""

    VERSION = 2

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the charger's address and probe it."""
        errors: dict[str, str] = {}

        if user_input is not None:
            data = _connection_data(user_input)
            await self.async_set_unique_id(
                f"{data[CONF_HOST]}:{data[CONF_PORT]}-{data[CONF_UNIT_ID]}"
            )
            self._abort_if_unique_id_configured()

            if await _async_probe(data):
                return self.async_create_entry(title="Peblar", data=data)
            errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input or {}
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user move the charger to a new address."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            data = _connection_data(user_input)
            if await _async_probe(data):
                return self.async_update_reload_and_abort(entry, data=data)
            errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, {**entry.data, **(user_input or {})}
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(entry: ConfigEntry) -> PeblarEvOptionsFlow:
        """Return the options flow."""
        return PeblarEvOptionsFlow()


class PeblarEvOptionsFlow(OptionsFlow):
    """Tunables: max current, heartbeat, watchdog timeout/fallback, pause guard."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show and store the tunables."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        return self.async_show_form(
            step_id="init",
            data_schema=_options_schema(dict(self.config_entry.options)),
        )
