# model/force_calibration.py

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ForceCalibration:
    """
    Simple linear calibration:
        F(N) = slope * (adc - adc_offset) + force_offset

    For most use-cases you can set force_offset = 0 and just use:
        F = slope * (adc - adc_offset)
    """
    slope: float          # N per ADC count
    adc_offset: float = 0.0
    force_offset: float = 0.0

    def adc_to_force(self, adc: float) -> float:
        return self.slope * (adc - self.adc_offset) + self.force_offset

    def force_to_adc(self, force: float) -> float:
        # inverse mapping
        return (force - self.force_offset) / self.slope + self.adc_offset

    @classmethod
    def from_two_point(cls, adc1: float, F1: float, adc2: float, F2: float):
        """
        Build a calibration from two known points:
            (adc1, F1) and (adc2, F2)
        """
        if adc2 == adc1:
            raise ValueError("adc1 and adc2 must be different")
        slope = (F2 - F1) / (adc2 - adc1)
        # choose adc_offset = adc1, force_offset = F1 so line passes through that point
        return cls(slope=slope, adc_offset=adc1, force_offset=F1)

    # ---- persistence helpers ----

    def save(self, path: str | Path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w") as f:
            json.dump(
                {
                    "slope": self.slope,
                    "adc_offset": self.adc_offset,
                    "force_offset": self.force_offset,
                },
                f,
                indent=2,
            )

    @classmethod
    def load(cls, path: str | Path) -> "ForceCalibration":
        path = Path(path)
        with path.open("r") as f:
            data = json.load(f)
        return cls(**data)