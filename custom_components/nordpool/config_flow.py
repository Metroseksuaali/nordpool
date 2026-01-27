"""Adds config flow for nordpool."""
import logging
import re
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.template import Template

from . import DOMAIN
from .sensor import _PRICE_IN, _REGIONS, DEFAULT_TEMPLATE

regions = sorted(list(_REGIONS.keys()))
currencys = sorted(list(set(v[0] for k, v in _REGIONS.items())))
price_types = sorted(list(_PRICE_IN.keys()))
_LOGGER = logging.getLogger(__name__)


class NordpoolFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Nordpool."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> "NordpoolOptionsFlowHandler":
        """Create the options flow."""
        return NordpoolOptionsFlowHandler()

    def __init__(self):
        """Initialize."""
        self._errors = {}

    async def async_step_user(
        self, user_input=None
    ):  # pylint: disable=dangerous-default-value
        """Handle a flow initialized by the user."""
        self._errors = {}

        if user_input is not None:
            template_ok = False
            if user_input["additional_costs"] in (None, ""):
                user_input["additional_costs"] = DEFAULT_TEMPLATE
            else:
                # Lets try to remove the most common mistakes, this will still fail if the template
                # was writte in notepad or something like that..
                user_input["additional_costs"] = re.sub(
                    r"\s{2,}", "", user_input["additional_costs"]
                )

            template_ok = await self._valid_template(user_input["additional_costs"])
            if template_ok:
                return self.async_create_entry(title="Nordpool", data=user_input)
            else:
                self._errors["base"] = "invalid_template"

        data_schema = {
            vol.Required("region", default=None): vol.In(regions),
            vol.Optional("currency", default=""): vol.In(currencys),
            vol.Optional("VAT", default=True): bool,
            vol.Optional("precision", default=3): vol.Coerce(int),
            vol.Optional("low_price_cutoff", default=1.0): vol.Coerce(float),
            vol.Optional("price_in_cents", default=False): bool,
            vol.Optional("price_type", default="kWh"): vol.In(price_types),
            vol.Optional("additional_costs", default=""): str,
        }

        placeholders = {
            "region": regions,
            "currency": currencys,
            "price_type": price_types,
            "additional_costs": "{{0.0|float}}",
        }

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(data_schema),
            description_placeholders=placeholders,
            errors=self._errors,
        )

    async def _valid_template(self, user_template):
        try:
            #
            ut = Template(user_template, self.hass).async_render(
                current_price=0,
            )  # Add current price as 0 as we dont know it yet..
            _LOGGER.debug("user_template %s value %s", user_template, ut)

            if isinstance(ut, float):
                return True
            else:
                return False
        except Exception as e:
            _LOGGER.error(e)
            pass
        return False

    async def async_step_import(self, user_input):  # pylint: disable=unused-argument
        """Import a config entry.
        Special type of import, we're not actually going to store any data.
        Instead, we're going to rely on the values that are in config file.
        """
        return self.async_create_entry(title="configuration.yaml", data={})


class NordpoolOptionsFlowHandler(OptionsFlow):
    """Handle Nordpool options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}

        if user_input is not None:
            if user_input.get("additional_costs"):
                user_input["additional_costs"] = re.sub(
                    r"\s{2,}", "", user_input["additional_costs"]
                )
                if not await self._valid_template(user_input["additional_costs"]):
                    errors["base"] = "invalid_template"
            else:
                user_input["additional_costs"] = DEFAULT_TEMPLATE

            if not errors:
                return self.async_create_entry(title="", data=user_input)

        # Get current values (options override data for existing entries)
        current = {**self.config_entry.data, **self.config_entry.options}

        options_schema = vol.Schema(
            {
                vol.Optional(
                    "currency", default=current.get("currency", "")
                ): vol.In(currencys),
                vol.Optional("VAT", default=current.get("VAT", True)): bool,
                vol.Optional(
                    "precision", default=current.get("precision", 3)
                ): vol.Coerce(int),
                vol.Optional(
                    "low_price_cutoff", default=current.get("low_price_cutoff", 1.0)
                ): vol.Coerce(float),
                vol.Optional(
                    "price_in_cents", default=current.get("price_in_cents", False)
                ): bool,
                vol.Optional(
                    "price_type", default=current.get("price_type", "kWh")
                ): vol.In(price_types),
                vol.Optional(
                    "additional_costs", default=current.get("additional_costs", "")
                ): str,
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=options_schema,
            errors=errors,
        )

    async def _valid_template(self, user_template: str) -> bool:
        """Validate Jinja2 template."""
        try:
            ut = Template(user_template, self.hass).async_render(current_price=0)
            return isinstance(ut, float)
        except Exception:
            return False
