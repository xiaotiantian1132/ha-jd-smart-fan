"""Fan platform for JD Smart electric fans (device category 102007).

This platform adds support for JD Smart electric fans (e.g. Airmate FA18-AD16),
which report Capitalized stream keys such as ``Power``, ``Wind`` and ``Mode``
(as opposed to the lower-case keys used by air conditioners).
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.percentage import (
    int_states_in_range,
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from .const import DEVICE_TYPE_FAN, FAN_REQUIRED_STREAMS
from .coordinator import JdSmartCoordinator, JdSmartConfigEntry
from .entity import JdSmartEntity

# ``Wind`` stream range: 0 (lowest) .. 11 (highest), as reported by the device.
WIND_RANGE = (0, 11)

# ``Mode`` stream values from the JD product template.
MODE_TO_PRESET = {
    "0": "normal",   # 普通模式 / normal
    "1": "smart",    # 智能模式 / smart
    "2": "auto",     # 自动模式 / auto
    "3": "sleep",    # 睡眠模式 / sleep
    "4": "soft",     # 柔和模式 / gentle
    "5": "cool",     # 冷房模式 / cooling
    "6": "silent",   # 静音模式 / silent
}
PRESET_TO_MODE = {value: key for key, value in MODE_TO_PRESET.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: JdSmartConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up JD Smart fans."""
    async_add_entities(
        JdSmartFan(coordinator)
        for coordinator in entry.runtime_data.coordinators.values()
        if coordinator.device_type == DEVICE_TYPE_FAN
        if (
            coordinator.data is None
            or FAN_REQUIRED_STREAMS <= coordinator.data.streams.keys()
        )
    )


class JdSmartFan(JdSmartEntity, FanEntity):
    """JD Smart electric fan entity."""

    _attr_name = None
    _attr_translation_key = "fan"
    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.PRESET_MODE
        | FanEntityFeature.OSCILLATE
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
    )
    _attr_speed_count = int_states_in_range(WIND_RANGE)
    _attr_preset_modes = list(PRESET_TO_MODE)

    def __init__(self, coordinator: JdSmartCoordinator) -> None:
        """Initialize the fan."""
        super().__init__(coordinator, "fan")
        streams = coordinator.data.streams if coordinator.data else None
        self._attr_supported_features = _supported_features(streams)

    @property
    def is_on(self) -> bool | None:
        """Return whether the fan is on."""
        power = self.streams.get("Power")
        if power is None:
            return None
        return power == "1"

    @property
    def percentage(self) -> int | None:
        """Return the current speed as a percentage."""
        wind = self.streams.get("Wind")
        if wind in (None, ""):
            return None
        try:
            return ranged_value_to_percentage(WIND_RANGE, int(wind))
        except (ValueError, TypeError):
            return None

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        return MODE_TO_PRESET.get(self.streams.get("Mode", ""))

    @property
    def oscillating(self) -> bool | None:
        """Return whether oscillation is on."""
        # Use Horizontal (left-right swing) as the primary oscillate state.
        value = self.streams.get("Horizontal")
        if value is None:
            return None
        return value == "1"

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan."""
        commands: dict[str, object] = {"Power": 1}
        if percentage is not None:
            commands["Wind"] = int(
                percentage_to_ranged_value(WIND_RANGE, percentage)
            )
        if preset_mode is not None:
            commands["Mode"] = int(PRESET_TO_MODE[preset_mode])
        await self._control(commands)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the fan."""
        await self._control({"Power": 0})

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the fan speed percentage."""
        value = int(percentage_to_ranged_value(WIND_RANGE, percentage))
        await self._control({"Wind": value})

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the fan preset mode."""
        await self._control({"Mode": int(PRESET_TO_MODE[preset_mode])})

    async def async_oscillate(self, oscillating: bool) -> None:
        """Turn oscillation on or off."""
        await self._control({"Horizontal": 1 if oscillating else 0})

    async def _control(self, commands: dict[str, object]) -> None:
        """Send control commands."""
        try:
            await self.coordinator.async_control_streams(commands)
        except Exception as err:
            raise HomeAssistantError("Unable to control JD Smart fan") from err


def _supported_features(streams: dict[str, str] | None) -> FanEntityFeature:
    """Return features supported by the available streams."""
    features = FanEntityFeature.TURN_ON | FanEntityFeature.TURN_OFF
    if streams is None:
        return (
            features
            | FanEntityFeature.SET_SPEED
            | FanEntityFeature.PRESET_MODE
            | FanEntityFeature.OSCILLATE
        )
    if "Wind" in streams:
        features |= FanEntityFeature.SET_SPEED
    if "Mode" in streams:
        features |= FanEntityFeature.PRESET_MODE
    if "Horizontal" in streams or "Vertical" in streams:
        features |= FanEntityFeature.OSCILLATE
    return features
