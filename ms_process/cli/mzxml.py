import argparse

from ms_process.mzxml_fix import fix_mz_ranges, validate, Precision


def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest='command')

    fix_parser = subparsers.add_parser('fix')
    fix_parser.add_argument('--zlib', action='store_true')
    fix_parser.add_argument('--precision', '-p', choices=(64, 32), type=int, default=64)
    fix_parser.add_argument('in_file')
    fix_parser.add_argument('out_file')

    validate_parser = subparsers.add_parser('validate')
    validate_parser.add_argument('in_file')

    args = parser.parse_args()
    if args.command == 'fix':
        fix_mz_ranges(args.in_file, args.out_file, args.zlib, Precision(args.precision))
    elif args.command == 'validate':
        validate(args.in_file)


if __name__ == '__main__':
    main()
