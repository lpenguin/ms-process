import os
from collections import deque
from contextlib import contextmanager
from typing import Dict, List, Tuple

import tqdm
from lxml import etree

from ms_process.processing.filters import Filter
from .data import Spectrum, BinaryDataArray, DataKind
from .xml_util import cleanup, LineEventsParser, ns


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


class SpectrumIterator:
    @staticmethod
    def _process_spectrum(parser: LineEventsParser)-> Spectrum:
        binary_arrays = {}  # type: Dict[DataKind, BinaryDataArray]
        for _, events in parser:
            for (action, elem) in events:
                if (action, elem.tag) == ('end', '{http://psi.hupo.org/ms/mzml}spectrum'):
                    return Spectrum(elem, binary_arrays)
                elif (action, elem.tag) == ('end', '{http://psi.hupo.org/ms/mzml}binaryDataArray'):
                    arr = BinaryDataArray.from_element(elem)
                    binary_arrays[arr.kind] = arr
        assert False

    def process(self, in_filename: str):
        with open_with_progress(in_filename) as in_f:
            parser = LineEventsParser(in_f)
            for _, events in parser:
                for (action, elem) in events:
                    if (action, elem.tag) == ('start', '{http://psi.hupo.org/ms/mzml}spectrum'):
                        spectrum = self._process_spectrum(parser)
                        cleanup(spectrum.elem)
                        yield spectrum


def parse_spectrum(parser: LineEventsParser)-> Spectrum:
    binary_arrays = {}  # type: Dict[DataKind, BinaryDataArray]
    for _, events in parser:
        for action, elem in events:
            if (action, elem.tag) == ('end', '{http://psi.hupo.org/ms/mzml}spectrum'):
                return Spectrum(elem, binary_arrays)
            elif (action, elem.tag) == ('end', '{http://psi.hupo.org/ms/mzml}binaryDataArray'):
                arr = BinaryDataArray.from_element(elem)
                binary_arrays[arr.kind] = arr
    assert False


def process_mzml(in_filename: str, out_filename: str, filters: List[Filter], last_ms1_specra_count: int=10):
    spectrum_offsets = []  # type: List[Tuple[str, int]]
    last_ms1_spectra = deque(maxlen=last_ms1_specra_count)

    with open_with_progress(in_filename) as in_f, \
            open(out_filename, 'w') as out_f:
        parser = LineEventsParser(in_f)

        def cvparam(accession: str, value: str, name: str):
            attrib = dict(cvRef="MS", accession=accession, value=value, name=name)
            return etree.Element('cvParam', attrib=attrib, nsmap=ns)

        def _handle_header():
            out_f.write('<indexedmzML xmlns="http://psi.hupo.org/ms/mzml" '
                        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
                        'xsi:schemaLocation="http://psi.hupo.org/ms/mzml '
                        'http://psidev.info/files/ms/mzML/xsd/mzML1.1.2_idx.xsd">\n')
            for line, events in parser:
                for action, elem in events:
                    if (action, elem.tag) == ('start', '{http://psi.hupo.org/ms/mzml}mzML'):
                        out_f.write(line)
                        _handle_mzml()
                        _write_index_and_end()
                        return

        def _process_spectrum(spectrum: Spectrum):
            spectrum_id = spectrum.elem.attrib['id']
            if 'scan' not in spectrum_id:
                spectrum_index = spectrum.elem.attrib['index']
                spectrum_id = 'scan={} '.format(spectrum_index) + spectrum_id
            spectrum.elem.attrib['id'] = spectrum_id

            if spectrum.ms_level == 1:
                for filter_ in filters:
                    filter_.apply_mut(spectrum, list(last_ms1_spectra))
                spectrum.mz.update_elem()
                spectrum.intensity.update_elem()
                last_ms1_spectra.append(spectrum)

            spectrum.elem.attrib['defaultArrayLength'] = str(int(spectrum.intensity.data.shape[0]))
            mz_data = spectrum.mz.data
            spectrum.elem.insert(0, cvparam("MS:1000528", str(mz_data.min()), "lowest observed m/z"))
            spectrum.elem.insert(0, cvparam("MS:1000527", str(mz_data.max()), "highest observed m/z"))

        def _handle_mzml():
            for line, events in parser:
                wrote_line = False
                for action, elem in events:
                    if (action, elem.tag) == ('end', '{http://psi.hupo.org/ms/mzml}mzML'):
                        out_f.write(line)
                        cleanup(elem)
                        return

                    if (action, elem.tag) == ('start', '{http://psi.hupo.org/ms/mzml}spectrum'):
                        offset = out_f.tell()
                        spectrum = parse_spectrum(parser)
                        _process_spectrum(spectrum)
                        spectrum_offsets.append((spectrum.elem.attrib['id'], offset))
                        out_f.write(etree.tostring(spectrum.elem).decode())
                        out_f.write('\n')
                        cleanup(spectrum.elem)
                    else:
                        if not wrote_line:
                            out_f.write(line)
                            wrote_line = True
                        if action == 'end':
                            cleanup(elem)

        def _write_index_and_end():
            index_list_offset = out_f.tell()
            out_f.write('<indexList count="1">\n')
            out_f.write('  <index name="spectrum">\n')
            for spectrum_id, offset in spectrum_offsets:
                out_f.write('    <offset idRef="{spectrum_id}">{offset}</offset>\n'.format(
                    spectrum_id=spectrum_id,
                    offset=offset,
                ))
            out_f.write('  </index>\n')
            out_f.write('</indexList>\n')
            out_f.write('<indexListOffset>{}</indexListOffset>\n'.format(index_list_offset))
            out_f.write('</indexedmzML>\n')

        _handle_header()
