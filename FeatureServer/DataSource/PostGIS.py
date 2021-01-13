__author__  = "MetaCarta"
__copyright__ = "Copyright (c) 2006-2008 MetaCarta"
__license__ = "Clear BSD"
__version__ = "$Id: PostGIS.py 615 2009-09-23 00:47:48Z jlivni $"

from psycopg2 import errorcodes

from FeatureServer.DataSource import DataSource
from vectorformats.Feature import Feature
from vectorformats.Formats import WKT

from FeatureServer.WebFeatureService.Response.InsertResult import InsertResult
from FeatureServer.WebFeatureService.Response.UpdateResult import UpdateResult
from FeatureServer.WebFeatureService.Response.DeleteResult import DeleteResult
from FeatureServer.WebFeatureService.Response.ReplaceResult import ReplaceResult

from FeatureServer.Exceptions.WebFeatureService.InvalidValueException import InvalidValueException
from FeatureServer.Exceptions.ConnectionException import ConnectionException

try:
    import psycopg2 as psycopg
except:
    import psycopg


import copy
import logging
import re
import datetime

try:
    import decimal
except:
    pass

class PostGIS (DataSource):
    """PostGIS datasource. Setting up the table is beyond the scope of
       FeatureServer."""

    query_action_types = ['lt', 'gt', 'ilike', 'like', 'gte', 'lte']

    query_action_sql = {'lt': '<', 'gt': '>',
                        'ilike': 'ilike', 'like':'like',
                        'gte': '>=', 'lte': '<=',
                        'eq': '='}

    def __init__(self, name, srid=4326, srid_out=4326, fid='gid',
                 geometry='the_geom', fe_attributes='true', order='',
                 attribute_cols='*', writable=True, encoding='utf-8',
                 schema='public', hstore='false', hstore_attr='', **kwargs):
        DataSource.__init__(self, name, **kwargs)
        self.schema         = schema.strip('" ')
        self.table          = kwargs["layer"].strip('" ')
        self.fid_col        = fid
        self.encoding       = encoding
        self.geom_col       = geometry
        self.order          = order
        self.srid           = srid
        self.srid_out       = srid_out
        self.db             = None
        self.dsn            = kwargs["dsn"]
        self.writable       = writable
        self.attribute_cols = attribute_cols
        self.fe_attributes = True

        if fe_attributes.lower() == 'false':
            self.fe_attributes  = False

        if hstore.lower() == 'true':
            self.hstore = True
            self.hstoreAttribute = hstore_attr
        else:
            self.hstore = False
            self.hstoreAttribute = "";

    def begin (self):
        try:
            self.db = psycopg.connect(self.dsn)
        except Exception as e:
            raise ConnectionException(**{'dump':str(e),'layer':self.name,'locator':'PostGIS','code':e.pgcode})

    def commit (self):
        if self.writable:
            self.db.commit()
        self.db.close()

    def rollback (self):
        if self.writable:
            self.db.rollback()
        self.db.close()

    def column_names (self, feature):
        return list(feature.properties.keys())

    def value_formats (self, feature):
        values = ["%%(%s)s" % self.geom_col]
        values = []
        for key, val in list(feature.properties.items()):
            valtype = type(val).__name__
            if valtype == "dict":
                val['pred'] = "%%(%s)s" % (key,)
                values.append(val)
            else:
                fmt     = "%%(%s)s" % (key, )
                values.append(fmt)
        return values

    def feature_predicates (self, feature):
        columns = self.column_names(feature)
        values  = self.value_formats(feature)
        predicates = []
        for pair in zip(columns, values):
            if pair[0] != self.geom_col:
                if isinstance(pair[1], dict):
                    # Special Query: pair[0] is 'a', pair[1] is {'type', 'pred', 'value'}
                    # We build a Predicate here, then we replace pair[1] with pair[1] value below
                    if 'value' in pair[1]:
                        predicates.append('"%s" %s %s' % (pair[1]['column'],
                                                          self.query_action_sql[pair[1]['type']],
                                                          pair[1]['pred']))

                else:
                    predicates.append('"%s" = %s' % pair)
        if feature.geometry and "coordinates" in feature.geometry:
            predicates.append(" %s = ST_SetSRID('%s'::geometry, %s) " % (self.geom_col, WKT.to_wkt(feature.geometry), self.srid))
        return predicates

    def feature_values (self, feature):
        props = copy.deepcopy(feature.properties)
        for key, val in props.items():
            if isinstance(val, str): ### b/c psycopg1 doesn't quote unicode
                props[key] = val.encode(self.encoding)
            if isinstance(val, dict):
                props[key] = val['value']
        return props


    def id_sequence (self):
        suffix =  '_' + self.fid_col + '_seq'
        table = self.table
        seq = ''
        if self.table[-1:] == '"':
            seq = table[:-1] + suffix + '"'
        else:
            seq = table + suffix

        return seq

    def insert (self, action):
        self.begin()

        cursor = self.db.cursor()

        if action.feature != None:
            feature = action.feature
            column_arr = self.column_names(feature) + [self.geom_col]
            columns = '"{}"'.format('", "'.join(column_arr))
            srid_wkt = "ST_SetSRID('{}'::geometry, {}) ".format(
                WKT.to_wkt(feature.geometry), self.srid)
            value_arr = self.value_formats(feature) + [srid_wkt]
            values = ", ".join(value_arr)

            sql = 'INSERT INTO "{}"."{}" ({}) VALUES ({}) RETURNING {}'.format(
                self.schema, self.table, columns, values, self.fid_col)

            attrs = self.feature_values(feature)
            logging.debug(cursor.mogrify(sql, attrs))

            try:
                cursor.execute(sql, attrs)
                action.id = cursor.fetchone()[0]
            except Exception as e:
                logging.error(e)

        elif action.wfsrequest != None:
            sql = action.wfsrequest.getStatement(self)

            logging.debug(sql)
            cursor.execute(sql)

            seq_sql = '''SELECT currval('"{}"."{}"'::regclass);'''.format(
                self.schema, self.id_sequence())
            cursor.execute(seq_sql)
            action.id = cursor.fetchone()[0]

        else:
            return None


        return InsertResult(action.id, '')


    def update (self, action):
        if action.feature != None:
            feature = action.feature
            predicates = ", ".join(self.feature_predicates(feature))
            attrs = self.feature_values(feature)
            attrs[self.fid_col] = action.id

            sql = 'UPDATE "{0}"."{1}" SET {2} WHERE "{3}" = %({3})s'.format(
                self.schema, self.table, predicates, self.fid_col)

            cursor = self.db.cursor()
            logging.debug(cursor.mogrify(sql, attrs))
            cursor.execute(sql, attrs)

            return UpdateResult(action.id, '')

        elif action.wfsrequest != None:
            sql = str(action.wfsrequest.getStatement(self))

            cursor = self.db.cursor()
            logging.debug(sql)
            cursor.execute(sql)

            return UpdateResult(action.id, '')

        return None

    def delete (self, action):
        attrs = {self.fid_col: action.id}
        if action.id != None:
            sql = 'DELETE FROM "{0}"."{1}" WHERE "{2}" = %({2})s'.format(
                self.schema, self.table, self.fid_col)

            cursor = self.db.cursor()
            logging.debug(cursor.mogrify(sql, attrs))
            cursor.execute(sql, attrs)

            return DeleteResult(action.id, '')

        elif action.wfsrequest != None:
            sql = action.wfsrequest.getStatement(self)

            cursor = self.db.cursor()
            logging.debug(cursor.mogrify(sql, attrs))
            cursor.execute(sql, attrs)

            return DeleteResult(action.id, '')

        return None


    def select (self, action):
        cursor = self.db.cursor()

        if action.id is not None:
            sql = ('SELECT ST_AsText(ST_Transform({0}, {1})) AS fs_text_geom, '
                   ''.format(self.geom_col, self.srid_out))

            if hasattr(self, 'version'):
                sql += '{} as version, '.format(self.version)
            if hasattr(self, 'ele'):
                sql += '{} as ele, '.format(self.ele)

            sql += '"{0}"'.format(self.fid_col)

            if len(self.attribute_cols) > 0:
                sql += ', {0}'.format(self.attribute_cols)

            if hasattr(self, 'additional_cols'):
                cols = self.additional_cols.split(';')
                additional_col = ','.join(cols)
                sql += ', {0}'.format(additional_col)
            attrs = {self.fid_col: str(action.id)}


            sql += ' FROM "{0}"."{1}" WHERE {2} = %%({3})s'.format(
                self.schema, self.table, self.fid_col, self.fid_col)

            logging.debug(cursor.mogrify(sql, attrs))
            cursor.execute(sql, attrs)

            result = [cursor.fetchone()]
        else:
            filters = []
            attrs   = {}
            if action.attributes:
                match = Feature(props = action.attributes)
                filters = self.feature_predicates(match)
                for key, value in list(action.attributes.items()):
                    if isinstance(value, dict):
                        attrs[key] = value['value']
                    else:
                        attrs[key] = value
            if action.bbox:
                bbox_def = "'BOX3D({0})::box3d'".format(', '.join(action.bbox))
                filters.append('ST_Intersects("{0}", ST_Transform('
                               'ST_SetSRID({1}, {2}), {3}))'.format(
                               self.geom_col, bbox_def, self.srid_out,
                               self.srid))
            cols = ['ST_AsText(ST_Transform("{0}", {1})) '
                    'AS fs_text_geom'.format(self.geom_col, self.srid_out)]
            if hasattr(self, 'ele'):
                ele = '"{0}" AS ele'.format(self.ele)
                cols.append(ele)
            if hasattr(self, 'version'):
                version = '"{0}" AS version'.format(self.version)
                cols.append(version)
            cols.append('"{0}"'.format(self.fid_col))

            if len(self.attribute_cols) > 0:
                cols.append(self.attribute_cols)

            # check OGC FE attributes
            if self.fe_attributes and action.wfsrequest:
                fe_cols = action.wfsrequest.getAttributes()
                ad_cols = self.getColumns()

                fe_cols = [x for x in fe_cols if x not in ad_cols]

                if len(fe_cols) > 0:
                    cols.extend(fe_cols)

            if hasattr(self, 'additional_cols'):
                cols.extend(self.additional_cols.split(';'))

            cols_def = ', '.join(cols)
            sql = 'SELECT {0} FROM "{1}"."{2}"'.format(cols_def, self.schema,
                                                       self.table)

            if filters:
                sql += ' WHERE ' + ' AND '.join(filters)

            if action.wfsrequest:
                sql += ' AND ' if filters else ' WHERE '
                sql += '{0}'.format(action.wfsrequest.render(self))

            if self.order:
                sql += ' ORDER BY {0}'.format(self.order)
            if action.maxfeatures:
                sql += ' LIMIT {0}'.format(str(action.maxfeatures))
            if action.startfeature:
                sql += ' OFFSET {0}'.format(str(action.startfeature))

            try:
                logging.debug(cursor.mogrify(sql, attrs))
                cursor.execute(sql, attrs)
            except Exception as e:
                if e.pgcode[:2] == errorcodes.CLASS_SYNTAX_ERROR_OR_ACCESS_RULE_VIOLATION:
                    raise InvalidValueException(dump=e.pgerror,
                                                layer=self.name,
                                                locator='PostGIS')

            result = cursor.fetchall() # should use fetchmany(action.maxfeatures)

        columns = [desc[0] for desc in cursor.description]
        features = []
        for row in result:
            props = dict(list(zip(columns, row)))
            if not props['fs_text_geom']:
                continue
            geom  = WKT.from_wkt(props['fs_text_geom'])
            id = props[self.fid_col]
            del props[self.fid_col]
            if self.attribute_cols == '*':
                del props[self.geom_col]
            del props['fs_text_geom']
            for key, value in list(props.items()):
                if isinstance(value, str):
                        props[key] = str(value, self.encoding)
                elif (isinstance(value, datetime.datetime)
                      or isinstance(value, datetime.date)):
                    # stringify datetimes
                    props[key] = str(value)

                try:
                    if isinstance(value, decimal.Decimal):
                            props[key] = str(str(value), self.encoding)
                except:
                    pass

            if (geom):
                features.append(Feature(id, geom, self.geom_col,
                                        self.srid_out, props))
        return features

    def getColumns(self):
        cols = []

        if hasattr(self, 'attribute_cols'):
            cols = self.attribute_cols.split(',')

        cols.append(self.geom_col)
        cols.append(self.fid_col)

        if hasattr(self, 'version'):
            cols.append(self.version)
        if hasattr(self, 'ele'):
            cols.append(self.ele)

        return cols


    def getAttributeDescription(self, attribute):
        self.begin()
        cursor = self.db.cursor()
        result = []

        sql = "SELECT t.typname AS type, a.attlen AS length FROM pg_class c, pg_attribute a, pg_type t "
        sql += "WHERE c.relname = '%s' and a.attname = '%s' and a.attnum > 0 and a.attrelid = c.oid and a.atttypid = t.oid ORDER BY a.attnum"

        try:
            cursor.execute(str(sql)% (self.table, attribute))
            result = [cursor.fetchone()]
            self.db.commit()
        except:
            pass

        type = 'string'
        length = ''

        if len(result) > 0:
            if result[0]:
                if str((result[0])[0]).lower().startswith('int'):
                    type = 'integer'
                    if int((result[0])[1]) == 4:
                        length = ''

        return (type, length)

    def getBBOX(self):
        self.begin()
        cursor = self.db.cursor()
        result = '-1 -1 -1 -1'
        sql = 'SELECT ST_Extent({0}) AS bbox FROM {1}'.format(self.geom_col, self.table)
        try:
            cursor.execute(sql)
            box = str(cursor.fetchone()[0]).strip()
            # returns 'BOX(minx, miny, maxx, maxy)'
            result = box[4:-1].replace(',', ' ')
            self.db.commit()
        except:
            pass
        return result
