from typing import List, Union, Optional, Tuple, TextIO, Iterable

from lxml import etree

ns = {'ns': 'http://psi.hupo.org/ms/mzml'}


def cleanup(elem: etree._Element):
    elem.clear()
    while elem.getprevious() is not None:
        del elem.getparent()[0]  # clean up preceding siblings


def xpath(element: etree._Element, xpath: str) -> List[Union[etree._Element, str]]:
    return element.xpath(xpath, namespaces=ns)


def attr(element: etree._Element, xpath: str) -> Optional[str]:
    res = element.xpath(xpath + '/@value', namespaces=ns)
    if res:
        return res[0]
    else:
        return None


Event = Tuple[str, Tuple[str, etree._Element]]


def iterate_events(f: TextIO)->Iterable[Event]:
    parser = etree.XMLPullParser(("start", "end"))
    for line in f:
        parser.feed(line.encode('ascii'))
        for action, elem in parser.read_events():
            yield line, (action, elem)