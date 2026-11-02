# Landing zone for external data

Roadmap `my_alloy_db_General_Road_Map_v2.md`, §1: the exact tables and
columns that hold each kind of value, for the lab's own data and for
external sources. Every new source must map into these, or into a small
number of carefully added tables. Written 2 November 2026 from the
migration files and `docs/database_schema.md`; schema `alloy_lab`.

Decision (2 Nov 2026, option B): external literature records live in
their own tables (`mce_literature_*`), not as rows of `samples`. They are
linked to the lab's samples through one composition key
(`stage_four/mce_nims/composition_key.py`).

## Composition / formula

| Where | Columns | Basis |
|---|---|---|
| `samples` (own samples) | `composition` JSONB | element → atomic fraction, sums to 1 |
| `compositions` (own samples, long format) | `sample_id`, `element`, `atomic_percent`, `weight_percent`, `composition_type` ('aimed' / 'measured' / 'reference') | at.% |
| `element_fraction_table.py` | wide view built on demand from `compositions` | at.% (not a table) |
| `mce_literature_records` (literature) | `metal_at_pct` JSONB, `interstitial_at_pct` JSONB, `composition_text`, `composition_details` | metals sum to 100 at.%; H/C/N/B relative to the metal total |
| **link** | `sample_composition_keys.composition_key` ↔ `mce_literature_records.composition_key`; view `mce_literature_matches` | key rule in `composition_key.py` |

## Source database + external ID (provenance)

| Where | Columns | Content |
|---|---|---|
| `literature_checks` | `source_db` ('materials_project' / 'oqmd' / 'alexandria', enforced from migration 008), `match_id` (e.g. 'mp-31186'), `match_formula`, `tier`, `checked_at`, `quality_flag` (migration 008, `'dft'`) | DFT database matches per own sample |
| `literature_sources` | `doi` (unique), `title`, `authors`, `year` | papers; DOIs from Materials Project synthesis records |
| `mce_literature_records` | `source`, `external_id` (unique together), `doi`, `article_ref`, `licence`, `quality_flag`, `retrieved_at` | external magnetocaloric records |

`quality_flag` values: `experimental_literature` (measured, curated from
papers, e.g. NIMS), `literature_mined` (text-mined), `unverified`
(automatic extraction not yet checked), `dft` (computed).

## Formation energy / energy above hull

| Where | Columns | Notes |
|---|---|---|
| `literature_checks` | `stability` | eV/atom above the convex hull; exact meaning differs slightly per database (`docs/literature_databases.md`) |

No formation-energy column exists yet; the Stage 3 CALPHAD feasibility
results are not stored in the database.

## Magnetic and magnetocaloric values

| Where | Columns | Basis / unit |
|---|---|---|
| `vsm_mh_details` (own) | `temperature_K`, `hc_oe`, `mr_emu`, `hc_mr_flag` | per hysteresis loop; Oe, emu |
| `vsm_mt_details`, `vsm_mt_candidates` (own) | `field_oe`; candidate `T_value` per branch (`candidate_kind`, `extremum_kind`) | transition-temperature *candidates*, not one value |
| `vsm_entropy_change` (own) | `target_field_oe`, `t_mid_k`, `delta_sm_j_per_kg_k` | ΔS_M(T) curve per field; field in Oe |
| `vsm_temperature_coefficients` (own) | `coefficient_type` ('beta_Hc' / 'alpha_Mr'), `coefficient_pct_per_k` | |
| `properties` (own, Stage 1 generic) | `property_name`, `property_value`, `property_unit`, `confidence_score` | linked to `characterization` |
| `mce_literature_records` (literature) | `t_tr_k`, `t_tr_source` ('reported' / 'dS_peak' / 'dTad_peak' / 'dS_dTad_mean'), `t_hys_k`, `h_tr_t` | K, T |
| `mce_literature_points` (literature) | `quantity` ('dS_max' / 'dT_ad_max'), `field_t`, `value`, `t_peak_k`, `fwhm_k` | peak values per field; field in tesla |

Mapping notes between own and literature values:
- Field: own data in Oe (`target_field_oe = 19000`), literature in T
  (`field_t = 1.9`). 1 T = 10 000 Oe.
- ΔS: own data are whole curves; literature has the peak |ΔS_M|max. The
  own peak is `max(|delta_sm_j_per_kg_k|)` per file and field.
- Transition temperature: own data store candidates (extrema of M and
  dM/dT); literature stores one value with its source. Comparing them
  needs an explicit choice of candidate.

## Gaps against the roadmap

- ~~`literature_checks` has no `quality_flag`~~ — added by
  `stage_four/mce_nims/008_literature_checks_provenance.sql` (roadmap §3,
  priority 1), with checks on `source_db` and `quality_flag` for new rows.
- No formation-energy column (see above).
