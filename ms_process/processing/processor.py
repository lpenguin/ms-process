import abc
from contextlib import contextmanager
from typing import Iterable, Dict, List, Optional, Tuple

import tqdm
from lxml import etree
import numpy as np
from scipy.signal import savgol_filter
import os

from .data import Spectrum, BinaryDataArray, DataKind
from .xml_util import Event, iterate_events, cleanup


class Filter(abc.ABC):
    @abc.abstractmethod
    def apply_mut(self, spectrum: Spectrum):
        pass


class ElectricNoiseFilter(Filter):
    def __init__(self, threshold_multiplier: int):
        self.threshold_multiplier = threshold_multiplier

    def apply_mut(self, spectrum: Spectrum):
        intensity = spectrum.intensity

        min_int = intensity.data[intensity.data > 0].min()
        threshold = self.threshold_multiplier * min_int
        new_intensity = intensity.data - threshold
        new_intensity[new_intensity < 0] = 0
        intensity.update_data(new_intensity)


class ResamplerFilter(Filter):
    def __init__(self, sampling_rate: float, mz_range: Optional[Tuple[float, float]]=None):
        self.mz_range = mz_range
        self.sampling_rate = sampling_rate

    def apply_mut(self, spectrum: Spectrum):
        mz = spectrum.mz
        intensity = spectrum.intensity

        if self.mz_range is not None:
            min_mz, max_mz = self.mz_range
        else:
            min_mz = mz.data.min()
            max_mz = mz.data.max()
        new_mz = np.arange(min_mz, max_mz, self.sampling_rate, dtype=mz.data.dtype)
        new_intensity = np.interp(new_mz, mz.data, intensity.data).astype(intensity.data.dtype)
        mz.update_data(new_mz)
        intensity.update_data(new_intensity)


class SGolayFilter(Filter):
    def __init__(self, window_length: int, polyorder: int):
        self.window_length = window_length
        self.polyorder = polyorder

    def apply_mut(self, spectrum: Spectrum):
        new_intensity = savgol_filter(
            x=spectrum.intensity.data,
            window_length=self.window_length,
            polyorder=self.polyorder
        ).astype(spectrum.intensity.data.dtype)
        new_intensity[new_intensity < 0] = 0
        spectrum.intensity.update_data(new_intensity)


@contextmanager
def open_with_progress(filename):
    size_bytes = os.stat(filename).st_size
    progress = tqdm.tqdm(total=size_bytes, unit_scale=True, unit='byte')

    def _it():
        with open(filename) as f:
            for line in f:
                progress.update(len(line))
                yield line

    yield _it()
    progress.close()


class SpectrumProcessor:
    @staticmethod
    def _process_spectrum(events: Iterable[Event])-> Spectrum:
        binary_arrays = {}  # type: Dict[DataKind, BinaryDataArray]
        for line, (action, elem) in events:
            if (action, elem.tag) == ('end', '{http://psi.hupo.org/ms/mzml}spectrum'):
                return Spectrum(elem, binary_arrays)
            elif (action, elem.tag) == ('end', '{http://psi.hupo.org/ms/mzml}binaryDataArray'):
                arr = BinaryDataArray.from_element(elem)
                binary_arrays[arr.kind] = arr
        assert False

    def process(self, in_filename: str):
        with open_with_progress(in_filename) as in_f:
            events = iterate_events(in_f)
            for line, (action, elem) in events:
                if (action, elem.tag) == ('start', '{http://psi.hupo.org/ms/mzml}spectrum'):
                    spectrum = self._process_spectrum(events)
                    cleanup(spectrum.elem)
                    yield spectrum

class Processor:
    def __init__(self, filters: List[Filter]):
        self.filters = filters

    @staticmethod
    def _process_spectrum(events: Iterable[Event])-> Spectrum:
        binary_arrays = {}  # type: Dict[DataKind, BinaryDataArray]
        for line, (action, elem) in events:
            if (action, elem.tag) == ('end', '{http://psi.hupo.org/ms/mzml}spectrum'):
                return Spectrum(elem, binary_arrays)
            elif (action, elem.tag) == ('end', '{http://psi.hupo.org/ms/mzml}binaryDataArray'):
                arr = BinaryDataArray.from_element(elem)
                binary_arrays[arr.kind] = arr
        assert False

    def process(self, in_filename: str, out_filename: str):
        with open(out_filename, 'w') as out_f, open_with_progress(in_filename) as in_f:
            events = iterate_events(in_f)

            for line, (action, elem) in events:
                if (action, elem.tag) == ('start', '{http://psi.hupo.org/ms/mzml}spectrum'):
                    spectrum = self._process_spectrum(events)

                    for filter_ in self.filters:
                        filter_.apply_mut(spectrum)
                    spectrum.elem.attrib['defaultArrayLength'] = str(int(spectrum.intensity.data.shape[0]))
                    out_f.write(etree.tostring(spectrum.elem).decode())
                    out_f.write('\n')
                    cleanup(spectrum.elem)
                else:
                    out_f.write(line)
                    if action == 'end':
                        cleanup(elem)