CREATE EXTENSION IF NOT EXISTS postgis;
DROP SCHEMA IF EXISTS test_featureserver CASCADE;
CREATE SCHEMA test_featureserver;

DROP TABLE IF EXISTS test_featureserver.asset_geom CASCADE;
CREATE TABLE IF NOT EXISTS test_featureserver.asset_geom (ogc_fid serial NOT NULL, id text, wkb_geometry geometry(Polygon,27700), CONSTRAINT asset_geom_ogc_fid_pk PRIMARY KEY (ogc_fid));

DROP TABLE IF EXISTS test_featureserver.asset_attr CASCADE;
CREATE TABLE test_featureserver.asset_attr (ogc_fid serial NOT NULL, id text, name text, start_date date, CONSTRAINT asset_attr_ogc_fid_pk PRIMARY KEY (ogc_fid));

INSERT INTO test_featureserver.asset_attr (id, name, start_date)
VALUES ('2PP',
        'Head Office',
        '2000-04-01');

INSERT INTO test_featureserver.asset_attr (id, name, start_date)
VALUES ('BLK',
        'Blackrod Rail Station',
        '2005-11-05');

INSERT INTO test_featureserver.asset_attr (id, name, start_date)
VALUES ('CTYTOW-CH',
        'City Tower Cycle Hub',
        '2010-06-23');

DROP VIEW IF EXISTS test_featureserver.assets;

-- Updatable view

CREATE VIEW test_featureserver.assets AS
SELECT g.ogc_fid,
       g.id,
       a.name,
       a.start_date,
       g.wkb_geometry
FROM test_featureserver.asset_geom g
LEFT JOIN test_featureserver.asset_attr a ON (g.id = a.id);

-- DROP RULE test_featureserver_asset_delete ON test_featureserver.assets;

CREATE OR REPLACE RULE test_featureserver_asset_delete AS ON
DELETE TO test_featureserver.assets DO INSTEAD
DELETE
FROM test_featureserver.asset_geom
WHERE asset_geom.ogc_fid = old.ogc_fid;

-- DROP RULE test_featureserver_asset_insert ON test_featureserver.assets;

CREATE OR REPLACE RULE test_featureserver_asset_insert AS ON
INSERT TO test_featureserver.assets DO INSTEAD
INSERT INTO test_featureserver.asset_geom (id, wkb_geometry)
VALUES (new.id,
        new.wkb_geometry) RETURNING asset_geom.ogc_fid,
                                               asset_geom.id,
                                               NULL::text AS name,
                                               NULL::date AS date,
                                               asset_geom.wkb_geometry;

-- DROP RULE test_featureserver_asset_update ON test_featureserver.assets;

CREATE OR REPLACE RULE test_featureserver_asset_update AS ON
UPDATE TO test_featureserver.assets DO INSTEAD
UPDATE test_featureserver.asset_geom
SET id = new.id,
    wkb_geometry = new.wkb_geometry
WHERE asset_geom.ogc_fid = old.ogc_fid RETURNING asset_geom.ogc_fid,
                                                            asset_geom.id,
                                                            NULL::text AS name,
                                                            NULL::date AS date,
                                                            asset_geom.wkb_geometry;


-- Manual testing of rules on view

-- INSERT INTO test_featureserver.assets (id, wkb_geometry) VALUES ('2PP', 'SRID=27700;Polygon((384247.04999999998835847 398093.04999999998835847, 384244.90000000002328306 398090.5, 384252.25 398084, 384263.5 398097.29999999998835847, 384266.25 398100.65000000002328306, 384268.04999999998835847 398099.20000000001164153, 384283 398117, 384284.54999999998835847 398118.84000000002561137, 384267.79999999998835847 398132.90999999997438863, 384267.45000000001164153 398132.5, 384254.5 398117.09999999997671694, 384258.25 398114, 384245.65000000002328306 398098.79999999998835847, 384249.15000000002328306 398095.54999999998835847, 384247.04999999998835847 398093.04999999998835847))') RETURNING ogc_fid;

-- SELECT * FROM test_featureserver.asset_geom;
-- SELECT * FROM test_featureserver.asset_attr;
-- SELECT * FROM test_featureserver.assets;

-- Test Rules

-- INSERT INTO test_featureserver.assets (id, wkb_geometry) VALUES ('BLK', 'SRID=27700;Polygon((384247.04999999998835847 398093.04999999998835847, 384244.90000000002328306 398090.5, 384252.25 398084, 384263.5 398097.29999999998835847, 384266.25 398100.65000000002328306, 384268.04999999998835847 398099.20000000001164153, 384283 398117, 384284.54999999998835847 398118.84000000002561137, 384267.79999999998835847 398132.90999999997438863, 384267.45000000001164153 398132.5, 384254.5 398117.09999999997671694, 384258.25 398114, 384245.65000000002328306 398098.79999999998835847, 384249.15000000002328306 398095.54999999998835847, 384247.04999999998835847 398093.04999999998835847))') RETURNING ogc_fid;

-- UPDATE test_featureserver.assets SET wkb_geometry = 'SRID=27700;Polygon((384247.04999999998835847 398093.04999999998835847, 384244.90000000002328306 398090.5, 384252.25 398084, 384263.5 398097.29999999998835847, 384266.25 398100.65000000002328306, 384268.04999999998835847 398099.20000000001164153, 384283 398117, 384284.54999999998835847 398118.84000000002561137, 384267.79999999998835847 398132.90999999997438863, 384267.45000000001164153 398132.5, 384254.5 398117.09999999997671694, 384258.25 398114, 384245.65000000002328306 398098.79999999998835847, 384249.15000000002328306 398095.54999999998835847, 384247.04999999998835847 398093.04999999998835847))' WHERE id = 'BLK';

-- DELETE FROM test_featureserver.assets WHERE id = 'BLK';
