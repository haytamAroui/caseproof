-- Upgrade the original sidecar JSONB column to byte-stable UTF-8 text.
alter table caseproof.ocr_geometry_sidecars drop constraint if exists ocr_geometry_sidecars_check;
alter table caseproof.ocr_geometry_sidecars alter column payload type text using payload::text;
alter table caseproof.ocr_geometry_sidecars drop constraint if exists ocr_geometry_text_budget;
alter table caseproof.ocr_geometry_sidecars add constraint ocr_geometry_text_budget check (octet_length(payload) <= 8388608);
