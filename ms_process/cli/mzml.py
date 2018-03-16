import argparse

from ms_process.mzml import process_file


def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest='command')

    filter_parser = subparsers.add_parser('filter')
    filter_parser.add_argument('--threshold-multiplier', default=3, type=int)
    filter_parser.add_argument('--mz-min-max', type=str, help='in format \"min:max\"')
    filter_parser.add_argument('in_file')
    filter_parser.add_argument('out_file')

    args = parser.parse_args()
    if args.command == 'filter':
        mz_min_max = None
        if args.mz_min_max:
            mz_min_max = [
                float(t)
                for t in args.mz_min_max.split(':')
            ]
            if len(mz_min_max) != 2:
                parser.error("Invalid --mz-min-max format")

        process_file(
            args.in_file,
            args.out_file,
            threshold_multiplier=args.threshold_multiplier,
            mz_min_max=mz_min_max
        )


if __name__ == '__main__':
    main()
