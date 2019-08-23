# ms-process

## Dependicies:
* Python >= 3.6

## Installation
```
git clone https://github.com/lpenguin/ms-process
cd ms-process
pip install .
```

## Usage
```
mzml -i <input.mzML> -o <output.mzML> --filter 'filter1:arg1,arg2,' --filter 'filter2:arg1,arg2'
```

## Filters
See `ms_process.processing.filters` and `ms_process.processing.mzml`
* `resample:<step,cetner_mz>`: Resample spectra
* `sgolay:<window_len,poly_order>`: Savitsky-Golay filter
* `baseline:<threshold>`: Remove all points from spectra with intensity less then <threshold>

* `index:<from,to>`: Keep spectra with index greater then <from> and less then <to>
* `rt`:<from,to>: Keep spectra with retention time (in seconds) greater then <from> and less then <to>.
* `mslevel:<ms_level>`: Keep spectra with ms level <ms_level>

* `compress:(compression_mz,compression_intensity)`: Change compression, possible values are: `none`, `zlib`, `numpress_linear`, `numpress_pic`
* `to_minutes`: Convert retention time units to minutes
* `type:<type_mz,type_intensity>`: Change data type, possible values are: `float32`, `float64`, `int32`

* `electric`: Deprecated
* `f32`: Deprecated