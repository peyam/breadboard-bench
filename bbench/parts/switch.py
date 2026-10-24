"""Single on/off switch (SPST): closed joins pins 1 and 2."""
from .base import Part, part, two


@part
class Switch(Part):
    TYPE, DESC, CATEGORY, ALIASES = "SW", "On/off switch", "switch", ("SPST",)
    PINS = two()
    DEFAULTS = {"closed": False}

    def __init__(self, ref="S?", **props):
        super().__init__(ref, **props)
        self.state = bool(self.props.get("closed", False))

    def links(self):
        return [(1, 2, "strong", 0.0, self.ref)] if self.state else []

    def set(self, value, section=None):
        self.state = bool(value)

    @property
    def closed(self):
        return self.state

    @closed.setter
    def closed(self, v):
        self.state = bool(v)
