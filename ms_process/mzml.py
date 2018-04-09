from typing import Optional, Tuple

import numpy as np
import sys

from .processing.processor import SpectrumIterator, process_mzml
from ms_process.processing.filters import ElectricNoiseFilter, ResamplerFilter, SGolayFilter, AsFloat32Filter


def process_file(in_filename: str,
                 out_filename: str,
                 threshold_multiplier: int,
                 resampler_step: float,
                 central_mz: float):
    sys.stderr.write("Processing data...\n")
    filters = [
        ElectricNoiseFilter(threshold_multiplier=threshold_multiplier),
        ResamplerFilter(sampling_rate=resampler_step, central_mz=central_mz),
        SGolayFilter(window_length=11, polyorder=4),
        AsFloat32Filter(),
    ]
    process_mzml(in_filename, out_filename, filters, last_ms1_specra_count=10)