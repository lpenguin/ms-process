from typing import Optional, NamedTuple, Union, Any

from lxml import etree

ns = {'ns': 'http://psi.hupo.org/ms/mzml'}

Element = etree._Element


class Cv(NamedTuple):
    accession: str
    name: str = None
    cv_ref: str = 'MS'


class CvRecord(NamedTuple):
    cv: Cv
    unit_cv: Optional[Cv] = None
    value: Optional[str] = None

    def value_as(self, type_):
        return type_(self.value)


class CvList:
    ms_level = Cv('MS:1000511', 'MS level')
    scan_start_time = Cv('MS:1000016', 'scan start time')

    lowest_observed_mz = Cv('MS:1000528', 'lowest observed m/z')
    highest_observed_mz = Cv('MS:1000527', 'highest observed m/z')

    data_kind_intensity = Cv('MS:1000515', 'intensity array')
    data_kind_mz = Cv('MS:1000514', 'm/z array')

    precision_f32 = Cv('MS:1000521', '32-bit float')
    precision_i32 = Cv('MS:1000519', '32-bit integer')
    precision_f64 = Cv('MS:1000523', '64-bit float')

    compression_none = Cv('MS:1000576', 'no compression')
    compression_zlib = Cv('MS:1000574', 'zlib compression')
    compression_numpress_linear = Cv('MS:1002312', 'MS-Numpress linear prediction compression')
    compression_numpress_pic = Cv('MS:1002313', 'MS-Numpress positive integer compression')

    unit_mz = Cv('MS:1000040', 'm/z')
    unit_intensity = Cv('MS:1000131', 'number of detector counts')

    unit_minute = Cv("UO:0000031", "minute", "UO")
    unit_second = Cv("UO:0000010", "second", "UO")


def get_cv(elem: Element, accession: Union[str, Cv]) -> Optional[Element]:
    if isinstance(accession, Cv):
        accession = accession.accession

    res = elem.xpath(f'ns:cvParam[@accession="{accession}"]', namespaces=ns)
    if len(res) > 0:
        return res[0]
    return None


def get_cv_record(elem: Element, cv: Union[str, Cv]) -> CvRecord:
    cv_elem = get_cv(elem, cv)
    attr = cv_elem.attrib
    unit_cv_accession = attr.get('unitAccession')
    unit_cv_name = attr.get('unitName')
    unit_cv_ref = attr.get('unitCvRef')
    value = attr.get('value')

    if unit_cv_accession is not None:
        unit_cv = Cv(unit_cv_accession, unit_cv_name, unit_cv_ref)
    else:
        unit_cv = None
    return CvRecord(cv=cv, unit_cv=unit_cv, value=value)


def has_cv(elem: Element, cv: Union[str, Cv]) -> bool:
    return get_cv(elem, cv) is not None


def remove_cv(elem: Element, accession: Union[str, Cv]) -> bool:
    cv = get_cv(elem, accession)
    if cv is not None:
        elem.remove(cv)
        return True
    return False


def add_cv(elem: Element, cv: Cv, value: Optional[Any] = None, unit_cv: Optional[Cv] = None) -> Element:
    remove_cv(elem, cv)
    attrib = dict(cvRef="MS", accession=cv.accession, name=cv.name)

    if value is not None:
        attrib.update(value=str(value))

    if unit_cv is not None:
        attrib.update(unitName=unit_cv.name, unitAccession=unit_cv.accession, unitCvRef='MS')

    cv_elem = etree.Element('cvParam', attrib=attrib, nsmap=ns, prefix='ns')
    elem.insert(0, cv_elem)
    return cv_elem
