-- M0.5: OCR sidecars must be removed with their exact document version.
-- The existing protected journey cleanup deletes document_versions after
-- deleting Storage; without this cascade it fails on persisted OCR geometry.
alter table caseproof.ocr_geometry_sidecars
  drop constraint ocr_geometry_sidecars_document_version_id_fkey;
alter table caseproof.ocr_geometry_sidecars
  add constraint ocr_geometry_sidecars_document_version_id_fkey
  foreign key (document_version_id)
  references caseproof.document_versions(id)
  on delete cascade;
