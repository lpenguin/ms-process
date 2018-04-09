import base64
import re
import zlib
from enum import Enum
from typing import Iterable, Tuple, List, TextIO, Iterator
import numpy as np


def iter_lines(f)->Iterable[Tuple[int, str]]:
    while True:
        line = f.readline()
        if not line:
            break
        yield (f.tell(), line)


class LinePatterns:
    SCAN_START = re.compile(r'\s*<scan')
    SCAN_END = re.compile(r'\s+</scan>')
    MS_RUN_END = re.compile(r'\s+</msRun>')
    PEAKS_END = re.compile(r'</peaks>\n')


# def iter_scans(line_iterator: Iterable[str])->Iterable[str]:
#     scan_lines = []
#     for pos, line in line_iterator:
#         if scan_lines:
#             scan_lines.append(line)
#         if line.startswith('    <scan'):
#             scan_lines = [line]
#         elif line.startswith('    </scan>'):
#             yield scan_lines
#             scan_lines = []
#         elif line.startswith('  </msRun>'):
#             break


class Precision(Enum):
    bit32 = 32
    bit64 = 64


def get_peaks_min_max(data_line: str, use_zlib: bool, precision: Precision)->Tuple[int, int]:
    data_start = data_line.index('>')
    data_end = data_line.index('<', data_start)
    data = data_line[data_start + 1: data_end]
    data_decoded = base64.b64decode(data)

    if use_zlib:
        data_decoded = zlib.decompress(data_decoded)

    dt = np.dtype(np.float64 if precision is Precision.bit64 else np.float32).newbyteorder('>')
    mz_int = np.frombuffer(data_decoded, dtype=dt)
    mz = mz_int.reshape((-1, 2))[:, 0]
    return mz.min(), mz.max()


def write_scan_lines(out_file: TextIO, scan_lines: Iterable[str], min_max: Tuple[float, float]):
    low_mz, high_mz = min_max
    it = iter(scan_lines)  # type: Iterator[str]

    first_scan_line = next(it).lstrip()
    first_scan_line = first_scan_line.replace('<scan', '<scan lowMz="{low_mz}" highMz="{high_mz}"'.format(
        low_mz=low_mz,
        high_mz=high_mz,
    ))
    out_file.write(first_scan_line)

    for scan_line in it:
        out_file.write(scan_line)


def write_scan_offsets(out_file: TextIO, scan_offsets: List[int]):
    out_file.write('<index name="scan">\n')
    for i, scan_offset in enumerate(scan_offsets):
        out_file.write('  <offset id="{}">{}</offset>\n'.format(i + 1, scan_offset))
    out_file.write('</index>\n')


def fix_mz_ranges(in_filename: str, out_filename: str, use_zlib: bool, presicion: Precision):
    with open(in_filename) as in_file, \
            open(out_filename, 'w') as out_file:
        scan_lines = []
        scan_offsets = []
        peak_stats = None
        index_offset = None
        for line in in_file:
            if scan_lines:
                scan_lines.append(line)
                # if LinePatterns.PEAKS_END.match(line):  #
                if line.endswith('</peaks>\n'):
                    # print("Peaks end")
                    peak_stats = get_peaks_min_max(line, use_zlib, presicion)
                if LinePatterns.SCAN_END.match(line):  # line.startswith('    </scan>'):
                    # print("Scan end")
                    scan_offset = out_file.tell()
                    scan_offsets.append(scan_offset)
                    write_scan_lines(out_file, scan_lines, peak_stats)
                    scan_lines = []
            else:
                if LinePatterns.SCAN_START.match(line):  # line.startswith('    <scan'):
                    # print("Scan start")
                    scan_lines = [line]
                elif LinePatterns.MS_RUN_END.match(line):  # line.startswith('  </msRun>'):
                    # print("Ms run end")
                    out_file.write(line)
                    index_offset = out_file.tell()
                    write_scan_offsets(out_file, scan_offsets)
                    out_file.write('<indexOffset>{}</indexOffset>\n'.format(index_offset))
                    out_file.write('  <sha1>804797ae1784bf722e3f168dec6c7b3669f781ae</sha1>\n')
                    out_file.write('</mzXML>')
                    break
                else:
                    out_file.write(line)


def validate(in_file):
    scan_offset_re = re.compile(r'\s*<offset id="\d+">(\d+)</offset>\n')
    index_offset_re = re.compile(r'\s*<indexOffset>(\d+)</indexOffset>\n')
    scan_offsets = []
    index_offset = None
    with open(in_file) as f:
        for line in f:
            m = scan_offset_re.match(line)
            if m is not None:
                scan_offsets.append(int(m.groups()[0]))
            m = index_offset_re.match(line)
            if m is not None:
                index_offset = int(m.groups()[0])

    with open(in_file) as f:
        for offset in scan_offsets:
            f.seek(offset)
            s = f.read(5)
            if s != '<scan':
                raise AssertionError('wrong scan offset: at {}, str: "{}"'.format(offset, s))
        print('Scan offsets OK')

        f.seek(index_offset)
        s = f.read(len('<index'))
        if s != '<index':
            raise AssertionError('wrong index offset: at {}, str:  "{}"'.format(index_offset, s))
        print('Index offset OK')

