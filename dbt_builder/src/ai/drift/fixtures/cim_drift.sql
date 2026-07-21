-- CIM drift dataset for Experiment 6 (Use Case B, RQ2).
--
-- Creates edh_unreg_silver_dev_st.cim_drifted as a controlled drift of the CIM
-- bronze schema. Empty tables (drift detection is schema-only). Each change is
-- annotated with its expert impact label; the machine-readable labels are in
-- cim_drift_labels.json (the answer key used to score H2b).
--
-- Scope: only cim_drifted is created; the bronze schema is never modified.
-- connectivity_nodes is INTENTIONALLY ABSENT -> it drifts to ORPHANED (breaking).

CREATE SCHEMA IF NOT EXISTS `edh_unreg_silver_dev_st`.`cim_drifted`;

-- conducting_equipment:
--   + owner STRING                 -> additive
--   - serial_number (removed)      -> breaking
--   mrid STRING -> BIGINT          -> breaking (high-risk business-key type change)
CREATE TABLE IF NOT EXISTS `edh_unreg_silver_dev_st`.`cim_drifted`.`conducting_equipment` (
  asset_status STRING,
  base_voltage_kv DOUBLE,
  cdc_flag STRING,
  equipment_type STRING,
  in_service BOOLEAN,
  load_dts TIMESTAMP,
  manufacturer STRING,
  model STRING,
  mrid BIGINT,            -- was STRING (breaking)
  name STRING,
  record_source STRING,
  owner STRING            -- added (additive)
  -- serial_number removed (breaking)
);

-- terminals:
--   sequence_number BIGINT -> DECIMAL(38,0) -> cosmetic (lossless widening, non-key)
--   + phase_code STRING                     -> additive
--   phases STRING -> INT                     -> breaking (incompatible type change)
CREATE TABLE IF NOT EXISTS `edh_unreg_silver_dev_st`.`cim_drifted`.`terminals` (
  cdc_flag STRING,
  conducting_equipment_mrid STRING,
  connected BOOLEAN,
  connectivity_node_mrid STRING,
  load_dts TIMESTAMP,
  mrid STRING,
  name STRING,
  phases INT,                    -- was STRING (breaking)
  record_source STRING,
  sequence_number DECIMAL(38,0), -- was BIGINT (cosmetic widening)
  phase_code STRING              -- added (additive)
);

-- cim_measurements: brand-new table absent from the approved contract -> additive (NEW).
CREATE TABLE IF NOT EXISTS `edh_unreg_silver_dev_st`.`cim_drifted`.`cim_measurements` (
  mrid STRING,
  measurement_type STRING,
  value DOUBLE,
  timestamp_utc TIMESTAMP,
  cdc_flag STRING,
  load_dts TIMESTAMP,
  record_source STRING
);

-- connectivity_nodes: intentionally NOT created -> ORPHANED (breaking).
