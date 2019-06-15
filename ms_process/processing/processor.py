import os
from collections import deque
from contextlib import contextmanager
from typing import Dict, List, Tuple

import tqdm
from lxml import etree, objectify

from ms_process.cv import add_cv, CvList, remove_cv
from ms_process.processing.filters import Filter, Predicate
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


def parse_spectrum(parser: LineEventsParser, spectrum_index: int)-> Spectrum:
    binary_arrays = {}  # type: Dict[DataKind, BinaryDataArray]
    for _, events in parser:
        for action, elem in events:
            if (action, elem.tag) == ('end', '{http://psi.hupo.org/ms/mzml}spectrum'):
                return Spectrum(elem, binary_arrays, spectrum_index)
            elif (action, elem.tag) == ('end', '{http://psi.hupo.org/ms/mzml}binaryDataArray'):
                arr = BinaryDataArray.from_element(elem)
                binary_arrays[arr.kind] = arr
    assert False


def process_mzml(in_filename: str,
                 out_filename: str,
                 last_ms1_specra_count: int,
                 filters: List[Filter],
                 predicates: List[Predicate]):

    spectrum_offsets = []  # type: List[Tuple[str, int]]
    last_ms1_spectra = deque(maxlen=last_ms1_specra_count)

    with open_with_progress(in_filename) as in_f, \
            open(out_filename, 'w') as out_f:
        parser = LineEventsParser(in_f)

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

        def _process_spectrum(spectrum: Spectrum)->bool:
            spectrum_id = spectrum.elem.attrib['id']
            if 'scan' not in spectrum_id:
                spectrum_index = spectrum.elem.attrib['index']
                spectrum_id = 'scan={} '.format(spectrum_index) + spectrum_id
            spectrum.elem.attrib['id'] = spectrum_id

            if not all(p.apply(spectrum, list(last_ms1_spectra)) for p in predicates):
                return False

            for filter_ in filters:
                filter_.apply_mut(spectrum, list(last_ms1_spectra))
            spectrum.mz.update_elem()
            spectrum.intensity.update_elem()
            last_ms1_spectra.append(spectrum)

            spectrum.elem.attrib['defaultArrayLength'] = str(int(spectrum.intensity.data.shape[0]))
            mz_data = spectrum.mz.data

            if mz_data.shape[0] > 0:
                add_cv(spectrum.elem, CvList.lowest_observed_mz, mz_data.min())
                add_cv(spectrum.elem, CvList.highest_observed_mz, mz_data.max())

            objectify.deannotate(spectrum.elem, xsi=True, xsi_nil=True, cleanup_namespaces=True)
            return True

        def _swallow_chrom_list(parser: LineEventsParser):
            for _, events in parser:
                for action, elem in events:
                    if (action, elem.tag) == ('end', '{http://psi.hupo.org/ms/mzml}chromatogramList'):
                        return
            assert False

        def _handle_mzml():
            spectrum_index = 0
            for line, events in parser:
                wrote_line = False
                for action, elem in events:
                    if (action, elem.tag) == ('end', '{http://psi.hupo.org/ms/mzml}mzML'):
                        out_f.write(line)
                        cleanup(elem)
                        return

                    if (action, elem.tag) == ('start', '{http://psi.hupo.org/ms/mzml}spectrum'):
                        offset = out_f.tell()
                        spectrum = parse_spectrum(parser, spectrum_index)
                        skip = not _process_spectrum(spectrum)

                        spectrum_index += 1
                        if skip:
                            continue
                        spectrum_offsets.append((spectrum.elem.attrib['id'], offset))
                        spectrum_str = etree.tostring(
                            spectrum.elem,
                            xml_declaration=False,
                            inclusive_ns_prefixes=False,
                            encoding='utf8',
                        )
                        # Stupid workaround
                        spectrum_str = spectrum_str.replace(
                            b'xmlns="http://psi.hupo.org/ms/mzml" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" ',
                            b'')
                        out_f.write(spectrum_str.decode())
                        out_f.write('\n')
                        cleanup(spectrum.elem)

                    # elif (action, elem.tag) == ('start', '{http://psi.hupo.org/ms/mzml}chromatogramList'):
                    #     _swallow_chrom_list(parser)
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
