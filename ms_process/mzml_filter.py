from .processing.processor import Processor, ElectricNoiseFilter, ResamplerFilter, SGolayFilter, SpectrumProcessor


def process_file(in_filename: str, out_filename: str, threshold_multiplier: int):
    print("Calculating mz min:max...")
    spectrum_processor = SpectrumProcessor()
    min_mz = float("inf")
    max_mz = -float("inf")

    for i, spectrum in enumerate(spectrum_processor.process(in_filename)):
        if spectrum.ms_level != '1':
            continue
        min_mz = min(min_mz, spectrum.mz.data.min())
        max_mz = max(max_mz, spectrum.mz.data.max())

    print("min mz: {min_mz}, max_mz: {max_mz}".format(min_mz=min_mz, max_mz=max_mz))
    print("Processing data...")
    filters = [
        ElectricNoiseFilter(threshold_multiplier=3),
        ResamplerFilter(sampling_rate=0.0043, mz_range=(min_mz, max_mz)),
        SGolayFilter(window_length=11, polyorder=4),
    ]
    processor = Processor(filters)
    processor.process(in_filename, out_filename)