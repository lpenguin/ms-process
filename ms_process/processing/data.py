import base64
import zlib
from enum import Enum
from typing import Dict
import PyMSNumpress


import numpy as np
from lxml import etree

from .xml_util import xpath
from ms_process.cv import remove_cv, CvList, add_cv, has_cv, get_cv_record


class DataKind(Enum):
    mz = 0
    intensity = 1


class Precision(Enum):
    float32 = 0
    float64 = 1
    int32 = 2


class Compression(Enum):
    none = 0
    zlib = 1
    numpress_linear = 2
    numpress_pic = 3


class BinaryDataArray:
    compression: Compression
    precision: Precision
    kind: DataKind
    elem: etree._Element
    data_raw: str
    _data: np.ndarray

    def __init__(self, elem: etree._Element, kind: DataKind, precision: Precision, compression: Compression,
                 data_raw: str):
        self.elem = elem
        self._data = None
        self.data_raw = data_raw
        self.compression = compression
        self.precision = precision
        self.kind = kind

    @property
    def data(self) -> np.ndarray:
        if self._data is not None:
            return self._data

        dtype = BinaryDataArray.dtype_from_precision(self.precision)
        compression = self.compression

        data = base64.b64decode(self.data_raw)
        if compression == Compression.zlib:
            data = zlib.decompress(data)
            data = np.frombuffer(data, dtype=dtype)
        elif compression == Compression.numpress_linear:
            result = []
            PyMSNumpress.decodeLinear(data, result)
            data = np.array(result, dtype=dtype)
        elif compression == Compression.numpress_pic:
            result = []
            PyMSNumpress.decodePic(data, result)
            data = np.array(result, dtype=dtype)
        elif compression == Compression.none:
            data = np.frombuffer(data, dtype=dtype)
        self._data = data
        return data

    @data.setter
    def data(self, value: np.ndarray):
        self._data = value


    @staticmethod
    def dtype_from_precision(precision: Precision) -> type:
        if precision == Precision.float32:
            return np.float32
        elif precision == Precision.float64:
            return np.float64
        elif precision == Precision.int32:
            return np.int32
        else:
            raise Exception(f"Invalid precision: {precision}")

    @staticmethod
    def from_element(elem: etree.Element) -> 'BinaryDataArray':
        if has_cv(elem, CvList.data_kind_intensity):
            kind = DataKind.intensity
        elif has_cv(elem, CvList.data_kind_mz):
            kind = DataKind.mz
        else:
            raise Exception('no kind cvParam')

        if has_cv(elem, CvList.precision_f64):
            precision = Precision.float64
        elif has_cv(elem, CvList.precision_f32):
            precision = Precision.float32
        elif has_cv(elem, CvList.precision_i32):
            precision = Precision.int32
        else:
            raise Exception('no precision cvParam')

        if has_cv(elem, CvList.compression_none):
            compression = Compression.none
        elif has_cv(elem, CvList.compression_zlib):
            compression = Compression.zlib
        elif has_cv(elem, CvList.compression_numpress_linear):
            compression = Compression.numpress_linear
        elif has_cv(elem, CvList.compression_numpress_pic):
            compression = Compression.numpress_pic
        else:
            raise Exception('no compression cvParam')

        data_raw = xpath(elem, 'ns:binary/text()')[0]
        return BinaryDataArray(
            elem=elem,
            kind=kind,
            precision=precision,
            compression=compression,
            data_raw=data_raw,
        )

    def update_elem(self):
        data_bytes = self.data.tobytes()
        if self.compression == Compression.zlib:
            data_bytes = zlib.compress(data_bytes)
        elif self.compression == Compression.numpress_pic:
            result = []
            PyMSNumpress.encodePic(self.data, result)
            data_bytes = bytes(result)
        elif self.compression == Compression.numpress_linear:
            result = []
            PyMSNumpress.encodeLinear(self.data, result, 700.0)
            data_bytes = bytes(result)
        data_bytes = base64.b64encode(data_bytes)

        binary_elem = xpath(self.elem, 'ns:binary')[0]
        binary_elem.text = data_bytes
        self.elem.attrib['encodedLength'] = str(len(data_bytes))

        for cv_el in xpath(self.elem, 'ns:cvParam'):
            self.elem.remove(cv_el)

        # to_delete = (
        #     CvList.compression_numpress_linear,
        #     CvList.compression_numpress_pic,
        #     CvList.compression_zlib,
        #     CvList.compression_none,
        #     CvList.precision_f32,
        #     CvList.precision_f64,
        #     CvList.precision_i32
        # )
        # for cv in to_delete:
        #     remove_cv(self.elem, cv)

        if self.precision == Precision.float32:
            add_cv(self.elem, CvList.precision_f32)
        elif self.precision == Precision.float64:
            add_cv(self.elem, CvList.precision_f64)
        elif self.precision == Precision.int32:
            add_cv(self.elem, CvList.precision_i32)

        if self.compression == Compression.none:
            add_cv(self.elem, CvList.compression_none)
        elif self.compression == Compression.zlib:
            add_cv(self.elem, CvList.compression_zlib)
        elif self.compression == Compression.numpress_linear:
            add_cv(self.elem, CvList.compression_numpress_linear)
        elif self.compression == Compression.numpress_pic:
            add_cv(self.elem, CvList.compression_numpress_pic)

        if self.kind == DataKind.intensity:
            add_cv(self.elem, CvList.data_kind_intensity)
        elif self.kind == DataKind.mz:
            add_cv(self.elem, CvList.data_kind_mz)

    def __repr__(self):
        return "<BinaryDataArray(kind={kind}, precision={precision}, " \
               "compression={compression}, data={data}...>".format(
            precision=self.precision,
            compression=self.compression,
            kind=self.kind,
            data=self.data[:5]
        )


class Spectrum:
    retention_time_seconds: float  # Seconds
    ms_level: float
    index: int

    def __init__(self, elem: etree.Element, binary_arrays: Dict[DataKind, BinaryDataArray], index: int):
        self.elem = elem
        self.index = index
        self.binary_arrays = binary_arrays
        self.ms_level = get_cv_record(elem, CvList.ms_level).value_as(int)

        scan = xpath(elem, 'ns:scanList/ns:scan')[0]
        scan_start_time_cv = get_cv_record(scan, CvList.scan_start_time)

        if scan_start_time_cv.unit_cv == CvList.unit_minute:
            self.retention_time_seconds = scan_start_time_cv.value_as(float) * 60
        else:
            self.retention_time_seconds = scan_start_time_cv.value_as(float)


    @property
    def intensity(self) -> BinaryDataArray:
        return self.binary_arrays[DataKind.intensity]

    @property
    def mz(self) -> BinaryDataArray:
        return self.binary_arrays[DataKind.mz]
