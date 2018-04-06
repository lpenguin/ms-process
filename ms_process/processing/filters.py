import abc
from typing import Optional, Tuple, List

import numpy as np
from lxml import etree
from scipy.signal import savgol_filter

from ms_process.processing.data import Spectrum, BinaryDataArray
from ms_process.processing.xml_util import xpath, ns


class Filter(abc.ABC):
    @abc.abstractmethod
    def apply_mut(self, spectrum: Spectrum, prev_spectra: List[Spectrum]):
        pass


class ElectricNoiseFilter(Filter):
    def __init__(self, threshold_multiplier: int):
        self.threshold_multiplier = threshold_multiplier

    def apply_mut(self, spectrum: Spectrum, prev_spectra: List[Spectrum]):
        intensity = spectrum.intensity

        min_int = intensity.data[intensity.data > 0].min()
        threshold = self.threshold_multiplier * min_int
        new_intensity = intensity.data - threshold
        new_intensity[new_intensity < 0] = 0
        intensity.data = new_intensity


class ResamplerFilter(Filter):
    def __init__(self, sampling_rate: float, mz_range: Optional[Tuple[float, float]]=None):
        self.mz_range = mz_range
        self.sampling_rate = sampling_rate

    def apply_mut(self, spectrum: Spectrum, prev_spectra: List[Spectrum]):
        mz = spectrum.mz
        intensity = spectrum.intensity

        if self.mz_range is not None:
            min_mz, max_mz = self.mz_range
        else:
            min_mz = mz.data.min()
            max_mz = mz.data.max()
        new_mz = np.arange(min_mz, max_mz, self.sampling_rate, dtype=mz.data.dtype)
        new_intensity = np.interp(new_mz, mz.data, intensity.data).astype(intensity.data.dtype)
        mz.data = new_mz
        intensity.data = new_intensity


class SGolayFilter(Filter):
    def __init__(self, window_length: int, polyorder: int):
        self.window_length = window_length
        self.polyorder = polyorder

    def apply_mut(self, spectrum: Spectrum, prev_spectra: List[Spectrum]):
        new_intensity = savgol_filter(
            x=spectrum.intensity.data,
            window_length=self.window_length,
            polyorder=self.polyorder
        ).astype(spectrum.intensity.data.dtype)
        new_intensity[new_intensity < 0] = 0
        spectrum.intensity.data = new_intensity


class AsFloat32Filter(Filter):
    def __init__(self):
        self.dtype = np.dtype(np.float32).newbyteorder('<')

    def to_f32(self, ba: BinaryDataArray):
        ba.data = ba.data.astype(self.dtype)
        for e in xpath(ba.elem, 'ns:cvParam[@accession="MS:1000523"]'):
            e.getparent().remove(e)
        attrib = dict(cvRef="MS", accession="MS:1000521", name="32-bit float")

        f32_el = etree.Element('cvParam', attrib=attrib, nsmap=ns, prefix='ns')
        ba.elem.insert(0, f32_el)

    def apply_mut(self, spectrum: Spectrum, prev_spectra: List[Spectrum]):
        self.to_f32(spectrum.mz)
        self.to_f32(spectrum.intensity)