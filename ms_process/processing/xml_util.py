from typing import List, Union, Optional, Tuple, TextIO, Iterable, Iterator

from lxml import etree

ns = {'ns': 'http://psi.hupo.org/ms/mzml'}


def cleanup(elem: etree.Element):
    elem.clear()
    while elem.getprevious() is not None:
        del elem.getparent()[0]  # clean up preceding siblings


def xpath(element: etree.Element, path: str) -> List[Union[etree.Element, str]]:
    return element.xpath(path, namespaces=ns)


def attr(element: etree.Element, path: str) -> Optional[str]:
    res = element.xpath(path + '/@value', namespaces=ns)
    if res:
        return res[0]
    else:
        return None


Event = Tuple[str, etree.Element]
# Event = Tuple[str, Tuple[str, etree._Element]]


# def iterate_events(f: TextIO)->Iterable[Event]:
#     parser = etree.XMLPullParser(("start", "end"))
#     for line in f:
#         parser.feed(line.encode('ascii'))
#         for action, elem in parser.read_events():
#             yield line, (action, elem)


class LineEventsParser:
    def __init__(self, f: Iterable[str]):
        self.parser = etree.XMLPullParser(("start", "end"))
        self.f_it = iter(f)

    def advance(self)->str:
        line = next(self.f_it)
        self.parser.feed(line.encode('ascii'))
        return line

    def events(self)->Iterable[Event]:
        return self.parser.read_events()

    def __iter__(self)->Iterable[Tuple[str, Iterable[Event]]]:
        while True:
            try:
                line = self.advance()
                events = self.events()
                yield line, events
                # for action, elem in events:
                #     if action == 'end':
                #         cleanup(elem)
            except StopIteration:
                break
