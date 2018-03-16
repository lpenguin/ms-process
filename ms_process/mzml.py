from typing import Optional, Tuple

import numpy as np
import sys

from .processing.processor import Processor, \
    ElectricNoiseFilter, ResamplerFilter, SGolayFilter, SpectrumIterator, AsFloat32Filter


def process_file(in_filename: str,
                 out_filename: str,
                 threshold_multiplier: int,
                 mz_min_max: Optional[Tuple[float, float]]=None):
    if mz_min_max is None:
        sys.stderr.write("Calculating mz min:max...\n")
        spectrum_processor = SpectrumIterator()
        min_mz = np.inf
        max_mz = -np.inf

        for i, spectrum in enumerate(spectrum_processor.process(in_filename)):
            if spectrum.ms_level != '1':
                continue
            min_mz = min(min_mz, spectrum.mz.data.min())
            max_mz = max(max_mz, spectrum.mz.data.max())
            # step_mean = np.abs(spectrum.mz.data[:-1] - spectrum.mz.data[1:]).mean()
            # step_std = np.abs(spectrum.mz.data[:-1] - spectrum.mz.data[1:]).std()
            # stats.append((min_mz, max_mz, step))
            # print("{}\t{}\t{}\t{}".format(min_mz, max_mz, step_mean, step_std))
    else:
        min_mz, max_mz = mz_min_max
    sys.stderr.write("min mz: {min_mz}, max_mz: {max_mz}\n".format(min_mz=min_mz, max_mz=max_mz))
    sys.stderr.write("Processing data...\n")
    filters = [
        ElectricNoiseFilter(threshold_multiplier=3),
        ResamplerFilter(sampling_rate=0.0043, mz_range=(min_mz, max_mz)),
        SGolayFilter(window_length=11, polyorder=4),
        AsFloat32Filter(),
    ]
    processor = Processor(filters)
    processor.process(in_filename, out_filename)