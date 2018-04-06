import argparse

from ms_process.mzml import process_file


def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest='command')

    filter_parser = subparsers.add_parser('filter')
    filter_parser.add_argument('--threshold-multiplier', default=3, type=int)
    filter_parser.add_argument('--central-mz', '-c', type=float, default=800, help='central mz in resampler')
    filter_parser.add_argument('in_file')
    filter_parser.add_argument('out_file')

    args = parser.parse_args()
    if args.command == 'filter':
        process_file(
            args.in_file,
            args.out_file,
            threshold_multiplier=args.threshold_multiplier,
            central_mz=args.central_mz,
        )


if __name__ == '__main__':
    main()
