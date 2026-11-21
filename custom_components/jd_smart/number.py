"""Number platform for JD Smart electric fans.

Exposes the fan speed (``Wind`` stream) as a dedicated number entity so it can
be named and controlled independently in HomeKit / voice assistants.
"""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DEVICE_TYPE_FAN
from .coordinator import JdSmartConfigEntry
from .entity import JdSmartEntity

# Wind stream accepts integer values 0 (lowest) .. 11 (highest).
WIND_MIN = 0
WIND_MAX = 11


async def async_setup_entry(
    hass: HomeAssistant,
    entry: JdSmartConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up JD Smart fan numbers."""
    async_add_entities(
        JdSmartFanNumber(coordinator)
        for coordinator in entry.runtime_data.coordinators.values()
        if coordinator.device_type == DEVICE_TYPE_FAN
        if coordinator.data is None or "Wind" in coordinator.data.streams
    )


class JdSmartFanNumber(JdSmartEntity, NumberEntity):
    """Fan speed number entity (Wind stream)."""

    entity_description = NumberEntityDescription(
        key="fan_wind",
        translation_key="fan_wind",
        native_min_value=WIND_MIN,
        native_max_value=WIND_MAX,
        native_step=1,
    )
    _attr_icon = "mdi:fan"

    def __init__(self, coordinator) -> None:
        """Initialize the fan speed number."""
        super().__init__(coordinator, "fan_wind")
        self.entity_description = NumberEntityDescription(
            key="fan_wind",
            translation_key="fan_wind",
            native_min_value=WIND_MIN,
            native_max_value=WIND_MAX,
            native_step=1,
        )

    @property
    def native_value(self) -> float | None:
        """Return current fan speed level."""
        value = self.streams.get("Wind")
        if value in (None, ""):
            return None
        try:
            return float(value)
        except ValueError:
            return None

    async def async_set_native_value(self, value: float) -> None:
        """Set fan speed level."""
        try:
            await self.coordinator.async_control_streams({"Wind": int(value)})
        except Exception as err:
            raise HomeAssistantError("Unable to control JD Smart fan") from err
