# SVT eMMC VIP Configuration

This page documents the local wrapper configuration for `src/sv/top/svt_emmc`.
The options are supplied by `models.py`, usually through YAML, then rendered into
the generated SystemVerilog configuration classes.

## Configuration Options

| YAML field | Default | Applies to | Generated target | Why this default is used |
| --- | ---: | --- | --- | --- |
| `card_type` | required | all | template branches | Selects eMMC, SD card, or SDIO generation. |
| `max_mem_data_width` | `4096` | all | ``SVT_MEM_MAX_DATA_WIDTH`` | Keeps the VIP memory data vector large enough for common transfers. |
| `power_ramp_up_time_ns` | `1000` | all | `timing_cfg.power_ramp_up_time_ns` | Accelerates power-up simulation by avoiding long default ramp waits. |
| `tsupply_rampup_min_ck` | `1` | all | `timing_cfg.tSupply_rampup_min_ck` | Uses the minimum legal supply ramp-up clock count; this value must stay greater than 0. |
| `tNac_hs200_hs400_ck` | `8` | all | `timing_cfg.tNac_hs200_hs400_ck` | Pins the low end of the original random range to reduce timing randomness in regressions. |
| `tNac_max_ck` | `8` | all | `timing_cfg.tNac_max_ck` | Keeps max response latency aligned with the fixed short timing profile. |
| `tNst_hs400_min_ck` | `2` | all | `timing_cfg.tNst_hs400_min_ck` | Pins the low end of the original HS400 strobe random range. |
| `tNst_hs400_max_ck` | `2` | all | `timing_cfg.tNst_hs400_max_ck` | Keeps HS400 strobe timing deterministic. |
| `emmc_ocr_vdd_access_mode` | `0` | eMMC only | `EMMC_OCR_REG_VDD_ACCESS_MODE_B30_B29` | Uses byte addressing for small-capacity VIP tests to avoid the known SVT eMMC Card VIP U-2022.12 sector-read data mismatch. |

## OCR Access Mode

`emmc_ocr_vdd_access_mode` controls the eMMC OCR access-mode field:

| Value | Meaning | Local recommendation |
| ---: | --- | --- |
| `0` | Byte mode | Default for this template family and recommended for small-capacity card tests. |
| `2` | Sector mode | Use only when modeling cards that require sector addressing, such as capacities above 2 GB, or after validating a fixed VIP. |
| `1`, `3` | Not used by the local default flow | Do not use unless an authorized VIP or device reference explicitly requires it. |

The default changed from sector mode (`2`) to byte mode (`0`) because the
user-provided debug screenshot identifies a closed failure chain in the
SVT eMMC Card VIP U-2022.12 sector-read branch: a 512-byte read can return real
data for the first 128 bytes and zeros for the remaining 384 bytes, which causes
readback compare mismatches. The byte-mode branch reads per byte and avoids that
VIP defect in small-capacity card scenarios.

This is a generated-card workaround, not a replacement for an SVT VIP source
fix. For large-capacity eMMC modeling where sector addressing is required, keep
`emmc_ocr_vdd_access_mode: 2` and use an upgraded or locally patched VIP.
