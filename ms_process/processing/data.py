import base64
import zlib
from enum import Enum
from typing import Dict

import numpy as np
from lxml import etree

from .xml_util import xpath, attr


class DataKind(Enum):
    mz = 0
    intensity = 1


class Precision(Enum):
    bit32 = 0
    bit64 = 1


class Compression(Enum):
    none = 0
    zlib = 1


class BinaryDataArray:
    def __init__(self, elem: etree._Element, kind: DataKind, precision: Precision, compression: Compression, data: np.ndarray):
        self.elem = elem
        self.data = data
        self.compression = compression
        self.precision = precision
        self.kind = kind

    @staticmethod
    def from_element(elem: etree._Element) -> 'BinaryDataArray':
        if xpath(elem, 'ns:cvParam[@accession="MS:1000515"]'):
            kind = DataKind.intensity
        elif xpath(elem, 'ns:cvParam[@accession="MS:1000514"]'):
            kind = DataKind.mz
        else:
            raise Exception('no kind cvParam')

        if xpath(elem, 'ns:cvParam[@accession="MS:1000523"]'):
            precision = Precision.bit64
        elif xpath(elem, 'ns:cvParam[@accession="MS:1000521"]'):
            precision = Precision.bit32
        else:
            raise Exception('no precision cvParam')

        if xpath(elem, 'ns:cvParam[@accession="MS:1000576"]'):
            compression = Compression.none
        elif xpath(elem, 'ns:cvParam[@accession="MS:1000574"]'):
            compression = Compression.zlib
        else:
            raise Exception('no compression cvParam')

        data = xpath(elem, 'ns:binary/text()')[0]
        data = base64.b64decode(data)
        if compression == Compression.zlib:
            data = zlib.decompress(data)

        dtype = np.dtype(np.float64 if precision is Precision.bit64 else np.float32).newbyteorder('<')
        data = np.frombuffer(data, dtype=dtype)

        return BinaryDataArray(
            elem=elem,
            kind=kind,
            precision=precision,
            compression=compression,
            data=data,
        )

    def update_data(self, data: np.ndarray):
        self.data = data
        data_bytes = self.data.tobytes()
        if self.compression == Compression.zlib:
            data_bytes = zlib.compress(data_bytes)
        data_bytes = base64.b64encode(data_bytes)

        binary_elem = xpath(self.elem, 'ns:binary')[0]
        binary_elem.text = data_bytes
        self.elem.attrib['encodedLength'] = str(len(data_bytes))

    def __repr__(self):
        return "<BinaryDataArray(kind={kind}, precision={precision}, " \
               "compression={compression}, data={data}...>".format(
            precision=self.precision,
            compression=self.compression,
            kind=self.kind,
            data=self.data[:5]
        )


class Spectrum:
    def __init__(self, elem: etree._Element, binary_arrays: Dict[DataKind, BinaryDataArray]):
        self.elem = elem
        self.binary_arrays = binary_arrays
        self.ms_level = attr(elem, 'ns:cvParam[@accession="MS:1000511"]')

    @property
    def intensity(self)->BinaryDataArray:
        return self.binary_arrays[DataKind.intensity]

    @property
    def mz(self)->BinaryDataArray:
        return self.binary_arrays[DataKind.mz]


