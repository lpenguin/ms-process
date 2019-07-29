import abc
import math
from typing import Optional, Tuple, List

import numpy as np
from lxml import etree
from scipy.signal import savgol_filter

from ms_process.processing.data import Spectrum, BinaryDataArray, Compression, Precision
from ms_process.processing.xml_util import xpath, ns
from ms_process.cv import remove_cv, add_cv, has_cv, get_cv, CvList, get_cv_record


arr1 = np.array([True])


def collapse_zero_intensity_mut(mz_data: BinaryDataArray, intensity_data: BinaryDataArray):
    mz = mz_data.data
    intensity = intensity_data.data

    N = 3
    cv = np.convolve((intensity > 0), np.ones((N,)) / N, mode='valid')
    cv = np.concatenate([arr1, cv, arr1])
    mz = mz[cv > 0]
    intensity = intensity[cv > 0]
    mz_data.data = mz
    intensity_data.data = intensity


class Filter(abc.ABC):
    @abc.abstractmethod
    def apply_mut(self, spectrum: Spectrum, prev_spectra: List[Spectrum]):
        pass


class Predicate(abc.ABC):
    @abc.abstractmethod
    def apply(self, spectrum: Spectrum, prev_spectra: List[Spectrum])->bool:
        pass


class RetentionTimePredicate(Predicate):
    def __init__(self, min_rt_sec: float, max_rt_sec: float):
        self.min_rt = min_rt_sec
        self.max_rt = max_rt_sec

    def apply(self, spectrum: Spectrum, prev_spectra: List[Spectrum]) -> bool:
        return self.min_rt <= spectrum.retention_time_seconds <= self.max_rt


class MsLevelFilter(Predicate):
    def __init__(self, ms_level: int):
        self.ms_level = ms_level

    def apply(self, spectrum: Spectrum, prev_spectra: List[Spectrum]) -> bool:
        return self.ms_level == spectrum.ms_level


class TypeFilter(Filter):
    def __init__(self, type_mz: str, type_intensity: str):
        self.type_mz = Precision[type_mz]
        self.type_intensity = Precision[type_intensity]

    def apply_mut(self, spectrum: Spectrum, prev_spectra: List[Spectrum]):
        spectrum.mz.precision = self.type_mz
        spectrum.mz.data = spectrum.mz.data.astype(BinaryDataArray.dtype_from_precision(self.type_mz))

        spectrum.intensity.precision = self.type_intensity
        spectrum.intensity.data = spectrum.intensity.data.astype(BinaryDataArray.dtype_from_precision(self.type_intensity))


class CompressionFilter(Filter):
    def __init__(self, compression_mz: str, compression_intensity: str):
        self.compression_mz = Compression[compression_mz]
        self.compression_intensity = Compression[compression_intensity]

    def apply_mut(self, spectrum: Spectrum, prev_spectra: List[Spectrum]):
        _ = spectrum.mz.data
        _ = spectrum.intensity.data
        spectrum.mz.compression = self.compression_mz
        spectrum.intensity.compression = self.compression_intensity


class IndexPredicate(Predicate):
    def __init__(self, min_index: int, count: int):
        self.min_index = min_index
        self.max_index = min_index + count - 1

    def apply(self, spectrum: Spectrum, prev_spectra: List[Spectrum]) -> bool:
        return self.min_index <= spectrum.index <= self.max_index


class ElectricNoiseFilter(Filter):
    def __init__(self, threshold_multiplier: int):
        self.threshold_multiplier = threshold_multiplier

    def apply_mut(self, spectrum: Spectrum, prev_spectra: List[Spectrum]):
        intensity = spectrum.intensity

        min_int = intensity.data[intensity.data > 0].min()
        threshold = self.threshold_multiplier * min_int
        new_intensity = intensity.data.copy()
        new_intensity[new_intensity < threshold] = 0
        intensity.data = new_intensity


class BaselineFilter(Filter):
    def __init__(self, threshold: float):
        self.threshold = threshold

    def apply_mut(self, spectrum: Spectrum, prev_spectra: List[Spectrum]):
        intensity = spectrum.intensity
        mz = spectrum.mz

        idata = np.clip(intensity.data - self.threshold, 0, np.inf)
        intensity.data = idata

        collapse_zero_intensity_mut(mz, intensity)

        # new_intensity = intensity.data.copy()
        # new_intensity[new_intensity < self.threshold] = 0
        # mz.data = mz.data[intensity.data > self.threshold]
        # intensity.data = intensity.data[intensity.data > self.threshold]
        # intensity.data = np.max(0, intensity.data - self.threshold)


class MzWindowFilter(Filter):
    def __init__(self, mz_max: float, mz_min: float):
        self.mz_max = mz_max
        self.mz_min = mz_min

    def apply_mut(self, spectrum: Spectrum, prev_spectra: List[Spectrum]):
        pred = (spectrum.mz.data >= self.mz_min) & (spectrum.mz.data <= self.mz_max)
        spectrum.mz.data = spectrum.mz.data[pred]
        spectrum.intensity.data = spectrum.intensity.data[pred]


class ResamplerFilter(Filter):
    def __init__(self, sampling_rate: float, central_mz: float):
        self.central_mz = central_mz
        self.sampling_rate = sampling_rate

    def apply_mut(self, spectrum: Spectrum, prev_spectra: List[Spectrum]):
        mz = spectrum.mz
        intensity = spectrum.intensity

        min_mz = self.central_mz - \
                 math.floor((self.central_mz - mz.data.min()) / self.sampling_rate) * self.sampling_rate

        max_mz = self.central_mz + \
                 math.ceil((mz.data.max() - self.central_mz) / self.sampling_rate) * self.sampling_rate

        new_mz = np.arange(min_mz, max_mz, self.sampling_rate, dtype=mz.data.dtype)
        new_intensity = np.interp(new_mz, mz.data, intensity.data).astype(intensity.data.dtype)
        mz.data = new_mz

        intensity.data = new_intensity
        collapse_zero_intensity_mut(mz, intensity)


class SGolayFilter(Filter):
    def __init__(self, window_length: int, polyorder: int):
        self.window_length = window_length
        self.polyorder = polyorder

    def apply_mut(self, spectrum: Spectrum, prev_spectra: List[Spectrum]):
        if spectrum.intensity.data.shape[0] < self.window_length:
            return
        new_intensity = savgol_filter(
            x=spectrum.intensity.data,
            window_length=self.window_length,
            polyorder=self.polyorder
        ).astype(spectrum.intensity.data.dtype)

        spectrum.mz.data = spectrum.mz.data[new_intensity > 0]
        spectrum.intensity.data = new_intensity[new_intensity > 0]

        collapse_zero_intensity_mut(spectrum.mz, spectrum.intensity)


class ConvertRtToMinutes(Filter):
    def apply_mut(self, spectrum: Spectrum, prev_spectra: List[Spectrum]):
        scan = xpath(spectrum.elem, 'ns:scanList/ns:scan')[0]
        scan_start_time = get_cv_record(scan, CvList.scan_start_time)
        if scan_start_time.unit_cv == CvList.unit_second:
            time = float(scan_start_time.value) / 60
            remove_cv(scan, CvList.scan_start_time)
            add_cv(scan, CvList.scan_start_time, value=time, unit_cv=CvList.unit_minute)


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