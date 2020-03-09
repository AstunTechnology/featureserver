CREATE EXTENSION postgis;
CREATE SCHEMA gis;
CREATE TABLE gis.polygons
(
  ogc_fid serial NOT NULL,
  name text,
  wkb_geometry geometry(Polygon,27700),
  CONSTRAINT polygons_ogc_fid_pk PRIMARY KEY (ogc_fid)
);
