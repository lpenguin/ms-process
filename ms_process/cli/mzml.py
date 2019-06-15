import argparse
import json
from typing import Union

from ms_process.mzml import process_file
from ms_process.processing.filters import AsFloat32Filter, ElectricNoiseFilter, SGolayFilter, ResamplerFilter, Filter, \
    ConvertRtToMinutes, BaselineFilter, IndexPredicate, RtWindowPredicate, Predicate, CompressionFilter, MsLevelFilter, \
    TypeFilter

modifier_map = {
    'resample': ResamplerFilter,
    'sgolay': SGolayFilter,
    'electric': ElectricNoiseFilter,
    'f32': AsFloat32Filter,
    'to_minutes': ConvertRtToMinutes,
    'baseline': BaselineFilter,
    'index': IndexPredicate,
    'rt': RtWindowPredicate,
    'compress': CompressionFilter,
    'mslevel': MsLevelFilter,
    'type': TypeFilter
}


def parse_filter(filter_str: str) -> Union[Filter, Predicate]:
    def _decode_value(_value: str):
        try:
            return json.loads(_value)
        except json.JSONDecodeError:
            return _value

    if ':' not in filter_str:
        name = filter_str
        params = []
    else:
        name, params_str = filter_str.split(':')
        if params_str:
            params = params_str.split(',')
            params = [
                _decode_value(p)
                for p in params
            ]
        else:
            params = []
    return modifier_map[name](*params)


def get_filter_descriptions():
    def _get_params(_filter_cls: type):
        annots = getattr(_filter_cls.__init__, '__annotations__', {})
        return ', '.join(
            f'{name}: {type_.__name__}'
            for name, type_ in annots.items())

    filter_descriptions = [
        f'{filter_name}({_get_params(filter_cls)})'
        for filter_name, filter_cls in modifier_map.items()
    ]
    return '\t, '.join(filter_descriptions)


def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest='command')


    filter_parser = subparsers.add_parser('filter', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    # filter_parser.add_argument('--threshold-multiplier', default=3, type=int, help='electric noise filter threshold')
    # filter_parser.add_argument('--central-mz', '-c', type=float, default=800, help='central mz in resampler')
    # filter_parser.add_argument('--step', type=float, default=0.0043, help='step in resampler')
    filter_parser.add_argument('--filter', action='append', default=[],
                               help=f'in format filter_name:parameter1,parameter2. Possible filters: {get_filter_descriptions()}')
    filter_parser.add_argument('--input', '-i', required=True)
    filter_parser.add_argument('--output', '-o', required=True)
    filter_parser.add_argument('--limit', type=int)
    filter_parser.add_argument('--offset', type=int)

    args = parser.parse_args()
    modifier = [
        parse_filter(f)
        for f in args.filter
    ]

    filters = [
        f for f in modifier
        if isinstance(f, Filter)
    ]

    predicates = [
        f for f in modifier
        if isinstance(f, Predicate)
    ]

    if args.command == 'filter':
        process_file(
            args.input,
            args.output,
            filters,
            predicates,
        )


if __name__ == '__main__':
    main()
