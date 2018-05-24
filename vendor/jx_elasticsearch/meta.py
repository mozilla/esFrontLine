# encoding: utf-8
#
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http:# mozilla.org/MPL/2.0/.
#
# Author: Kyle Lahnakoski (kyle@lahnakoski.com)
#
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals

import itertools
from itertools import product

import jx_base
from jx_base.namespace import Namespace
from mo_math import MAX

from mo_collections.relation import Relation_usingList

from jx_base import STRUCT, TableDesc, BOOLEAN
from jx_base.query import QueryOp
from jx_python import jx, meta as jx_base_meta
from jx_python.containers.list_usingPythonList import ListContainer
from jx_python.meta import ColumnList, Column
from mo_dots import Data, relative_field, SELF_PATH, ROOT_PATH, coalesce, set_default, Null, split_field, join_field, wrap, concat_field, startswith_field, literal_field
from mo_json.typed_encoder import EXISTS_TYPE, TYPE_PREFIX, untype_path, unnest_path
from mo_kwargs import override
from mo_logs import Log
from mo_logs.strings import quote
from mo_threads import Queue, THREAD_STOP, Thread, Till
from mo_times import HOUR, MINUTE, Timer, Date
from pyLibrary.env import elasticsearch
from pyLibrary.env.elasticsearch import es_type_to_json_type, _get_best_type_from_mapping

MAX_COLUMN_METADATA_AGE = 12 * HOUR
ENABLE_META_SCAN = False
DEBUG = False
TOO_OLD = 2*HOUR
OLD_METADATA = MINUTE
TEST_TABLE_PREFIX = "testing"  # USED TO TURN OFF COMPLAINING ABOUT TEST INDEXES


class ElasticsearchMetadata(Namespace):
    """
    MANAGE SNOWFLAKE SCHEMAS FOR EACH OF THE ALIASES FOUND IN THE CLUSTER
    """

    def __new__(cls, *args, **kwargs):
        if jx_base_meta.singlton:
            return jx_base_meta.singlton
        else:
            jx_base_meta.singlton = object.__new__(cls)
            return jx_base_meta.singlton

    @override
    def __init__(self, host, index, sql_file='metadata.sqlite', alias=None, name=None, port=9200, kwargs=None):
        if hasattr(self, "settings"):
            return

        self.too_old = TOO_OLD
        self.settings = kwargs
        self.default_name = coalesce(name, alias, index)
        self.es_cluster = elasticsearch.Cluster(kwargs=kwargs)
        self.index_does_not_exist = set()
        self.todo = Queue("refresh metadata", max=100000, unique=True)

        self.index_to_alias = Relation_usingList()


        self.es_metadata = Null
        # self.abs_columns = set()
        self.last_es_metadata = Date.now()-OLD_METADATA

        self.meta = Data()
        self.meta.columns = ColumnList()

        self.alias_to_query_paths = {
            "meta.columns": [['.']],
            "meta.tables": [['.']]
        }
        self.alias_new_since = {
            "meta.columns": Date.now(),
            "meta.tables": Date.now()
        }
        table_columns = metadata_tables()
        self.meta.tables = ListContainer("meta.tables", [], jx_base.Schema(".", table_columns))
        self.meta.columns.extend(table_columns)
        # TODO: fix monitor so it does not bring down ES
        if ENABLE_META_SCAN:
            self.worker = Thread.run("refresh metadata", self.monitor)
        else:
            self.worker = Thread.run("refresh metadata", self.not_monitor)
        return

    @property
    def url(self):
        return self.es_cluster.path + "/" + self.default_name.replace(".", "/")

    def _reload_columns(self, alias=None):
        """
        :param alias: A REAL ALIAS (OR NAME OF INDEX THAT HAS NO ALIAS)
        :return:
        """
        # FIND ALL INDEXES OF ALIAS
        canonical_index = self.es_cluster.get_best_matching_index(alias).index
        times = self.es_cluster.index_new_since

        indexes = self.index_to_alias.get_domain(alias)
        update_required = not (MAX(times[i] for i in indexes) < self.es_cluster.last_metadata)
        metadata = self.es_cluster.get_metadata(force=update_required)

        props = [
            # (index, type, properties) TRIPLE
            (self.es_cluster.get_index(index=i, type=t, debug=DEBUG), t, m.properties)
            for i, d in metadata.indices.items()
            if i in indexes
            for t, m in [_get_best_type_from_mapping(d.mappings)]
        ]

        # CONFIRM ALL COLUMNS ARE SAME, FIX IF NOT
        dirty = False
        all_comparisions = list(jx.pairwise(props)) + list(jx.pairwise(jx.reverse(props)))
        # NOTICE THE SAME (index, type, properties) TRIPLE FROM ABOVE
        for (i1, t1, p1), (i2, t2, p2) in all_comparisions:
            diff = elasticsearch.diff_schema(p2, p1)
            if not self.settings.read_only:
                for d in diff:
                    dirty = True
                    i1.add_property(*d)
        meta = self.es_cluster.get_metadata(force=dirty).indices[canonical_index]

        data_type, mapping = _get_best_type_from_mapping(meta.mappings)
        mapping.properties["_id"] = {"type": "string", "index": "not_analyzed"}
        self._parse_properties(alias, mapping, meta)

    def _parse_properties(self, alias, mapping, meta):
        abs_columns = elasticsearch.parse_properties(alias, None, mapping.properties)
        with Timer("upserting {{num}} columns", {"num": len(abs_columns)}, debug=DEBUG):
            # LIST OF EVERY NESTED PATH
            query_paths = [[c.es_column] for c in abs_columns if c.es_type == "nested"]
            for a, b in itertools.product(query_paths, query_paths):
                aa = a[0]
                bb = b[0]
                if aa and bb.startswith(aa):
                    for i, b_prefix in enumerate(b):
                        if len(b_prefix) > len(aa):
                            continue
                        if aa == b_prefix:
                            break  # SPLIT ALREADY FOUND
                        b.insert(i, aa)
                        break
            for q in query_paths:
                q.append(SELF_PATH)
            query_paths.append(ROOT_PATH)
            self.alias_to_query_paths[alias] = query_paths

            # ADD RELATIVE NAMES
            for abs_column in abs_columns:
                abs_column.last_updated = None
                abs_column.jx_type = es_type_to_json_type[abs_column.es_type]
                for query_path in query_paths:
                    abs_column.names[query_path[0]] = relative_field(abs_column.names["."], query_path[0])
                self.todo.add(self.meta.columns.add(abs_column))
        pass

    def query(self, _query):
        return self.meta.columns.query(QueryOp(set_default(
            {
                "from": self.meta.columns,
                "sort": ["table", "name"]
            },
            _query.__data__()
        )))

    def get_columns(self, table_name, column_name=None, force=False):
        """
        RETURN METADATA COLUMNS
        """
        table_path = split_field(table_name)
        root_table_name = table_path[0]

        # FIND ALIAS
        if root_table_name in self.alias_new_since:
            alias = root_table_name
        else:
            alias = self.index_to_alias[root_table_name]

        if not alias:
            self.es_cluster.get_metadata(force=True)
            # ENSURE INDEX -> ALIAS IS IN A MAPPING FOR LATER
            for a in self.es_cluster.get_aliases():
                self.alias_new_since[a.alias] = MAX([self.es_cluster.index_new_since[a.index], self.alias_new_since.get(a.alias)])
                self.index_to_alias[a.index] = coalesce(a.alias, a.index)

            if root_table_name in self.alias_new_since:
                alias = root_table_name
            else:
                alias = self.index_to_alias[root_table_name]

            if not alias:
                Log.error("{{table|quote}} does not exist", table=table_name)

        now = Date.now()
        table = self.get_table(alias)[0]

        try:
            # LAST TIME WE GOT INFO FOR THIS TABLE
            if not table:
                table = TableDesc(
                    name=alias,
                    url=None,
                    query_path=['.'],
                    timestamp=Date.now()
                )
                with self.meta.tables.locker:
                    self.meta.tables.add(table)
                self._reload_columns(alias=alias)
            elif force or table.timestamp < now - MAX_COLUMN_METADATA_AGE:
                table.timestamp = now
                self._reload_columns(alias=alias)

            columns = self.meta.columns.find(alias, column_name)
            columns = jx.sort(columns, "names.\.")
            # AT LEAST WAIT FOR THE COLUMNS TO UPDATE
            while len(self.todo) and not all(columns.get("last_updated")):
                if DEBUG:
                    if len(columns) > 10:
                        Log.note("waiting for {{num}} columns to update", num=len([c for c in columns if not c.last_updated]))
                    else:
                        Log.note("waiting for columns to update {{columns|json}}", columns=[c.es_index+"."+c.es_column for c in columns if not c.last_updated])
                Till(seconds=1).wait()
            return columns
        except Exception as e:
            Log.error("Not expected", cause=e)

        return []

    def _update_cardinality(self, column):
        """
        QUERY ES TO FIND CARDINALITY AND PARTITIONS FOR A SIMPLE COLUMN
        """
        if column.es_index in self.index_does_not_exist:
            return

        if column.jx_type in STRUCT:
            Log.error("not supported")
        try:
            if column.es_index == "meta.columns":
                partitions = jx.sort([g[column.es_column] for g, _ in jx.groupby(self.meta.columns, column.es_column) if g[column.es_column] != None])
                self.meta.columns.update({
                    "set": {
                        "partitions": partitions,
                        "count": len(self.meta.columns),
                        "cardinality": len(partitions),
                        "multi": 1,
                        "last_updated": Date.now()
                    },
                    "where": {"eq": {"es_index": column.es_index, "es_column": column.es_column}}
                })
                return
            if column.es_index == "meta.tables":
                partitions = jx.sort([g[column.es_column] for g, _ in jx.groupby(self.meta.tables, column.es_column) if g[column.es_column] != None])
                self.meta.columns.update({
                    "set": {
                        "partitions": partitions,
                        "count": len(self.meta.tables),
                        "cardinality": len(partitions),
                        "multi": 1,
                        "last_updated": Date.now()
                    },
                    "where": {"eq": {"es_index": column.es_index, "es_column": column.es_column}}
                })
                return

            es_index = column.es_index.split(".")[0]

            is_text = [cc for cc in self.meta.columns if cc.es_column == column.es_column and cc.es_type == "text"]
            if is_text:
                # text IS A MULTIVALUE STRING THAT CAN ONLY BE FILTERED
                result = self.es_cluster.post("/" + es_index + "/_search", data={
                    "aggs": {
                        "count": {"filter": {"match_all": {}}}
                    },
                    "size": 0
                })
                count = result.hits.total
                cardinality = 1001
                multi = 1001
            elif column.es_column == "_id":
                result = self.es_cluster.post("/" + es_index + "/_search", data={
                    "query": {"match_all": {}},
                    "size": 0
                })
                count = cardinality = result.hits.total
                multi = 1
            elif column.es_type == BOOLEAN:
                result = self.es_cluster.post("/" + es_index + "/_search", data={
                    "aggs": {
                        "count": _counting_query(column)
                    },
                    "size": 0
                })
                count = result.hits.total
                cardinality = 2
                multi = 1
            else:
                result = self.es_cluster.post("/" + es_index + "/_search", data={
                    "aggs": {
                        "count": _counting_query(column),
                        "multi": {"max": {"script": "doc[" + quote(column.es_column) + "].values.size()"}}
                    },
                    "size": 0
                })
                agg_results = result.aggregations
                count = result.hits.total
                cardinality = coalesce(agg_results.count.value, agg_results.count._nested.value, agg_results.count.doc_count)
                multi = int(coalesce(agg_results.multi.value, 1))
                if cardinality == None:
                   Log.error("logic error")

            query = Data(size=0)

            if column.es_column == "_id":
                self.meta.columns.update({
                    "set": {
                        "count": cardinality,
                        "cardinality": cardinality,
                        "multi": 1,
                        "last_updated": Date.now()
                    },
                    "clear": ["partitions"],
                    "where": {"eq": {"es_index": column.es_index, "es_column": column.es_column}}
                })
                return
            elif cardinality > 1000 or (count >= 30 and cardinality == count) or (count >= 1000 and cardinality / count > 0.99):
                if DEBUG:
                    Log.note("{{table}}.{{field}} has {{num}} parts", table=column.es_index, field=column.es_column, num=cardinality)
                self.meta.columns.update({
                    "set": {
                        "count": count,
                        "cardinality": cardinality,
                        "multi": multi,
                        "last_updated": Date.now()
                    },
                    "clear": ["partitions"],
                    "where": {"eq": {"es_index": column.es_index, "es_column": column.es_column}}
                })
                return
            elif column.es_type in elasticsearch.ES_NUMERIC_TYPES and cardinality > 30:
                if DEBUG:
                    Log.note("{{field}} has {{num}} parts", field=column.es_index, num=cardinality)
                self.meta.columns.update({
                    "set": {
                        "count": count,
                        "cardinality": cardinality,
                        "multi": multi,
                        "last_updated": Date.now()
                    },
                    "clear": ["partitions"],
                    "where": {"eq": {"es_index": column.es_index, "es_column": column.es_column}}
                })
                return
            elif len(column.nested_path) != 1:
                query.aggs["_"] = {
                    "nested": {"path": column.nested_path[0]},
                    "aggs": {"_nested": {"terms": {"field": column.es_column}}}
                }
            elif cardinality == 0:
                query.aggs["_"] = {"terms": {"field": column.es_column}}
            else:
                query.aggs["_"] = {"terms": {"field": column.es_column, "size": cardinality}}

            result = self.es_cluster.post("/" + es_index + "/_search", data=query)

            aggs = result.aggregations._
            if aggs._nested:
                parts = jx.sort(aggs._nested.buckets.key)
            else:
                parts = jx.sort(aggs.buckets.key)

            self.meta.columns.update({
                "set": {
                    "count": count,
                    "cardinality": cardinality,
                    "multi": multi,
                    "partitions": parts,
                    "last_updated": Date.now()
                },
                "where": {"eq": {"es_index": column.es_index, "es_column": column.es_column}}
            })
        except Exception as e:
            # CAN NOT IMPORT: THE TEST MODULES SETS UP LOGGING
            # from tests.test_jx import TEST_TABLE
            TEST_TABLE = "testdata"
            is_missing_index = any(w in e for w in ["IndexMissingException", "index_not_found_exception"])
            is_test_table = any(column.es_index.startswith(t) for t in [TEST_TABLE_PREFIX, TEST_TABLE])
            if is_missing_index and is_test_table:
                # WE EXPECT TEST TABLES TO DISAPPEAR
                self.meta.columns.update({
                    "clear": ".",
                    "where": {"eq": {"es_index": column.es_index}}
                })
                self.index_does_not_exist.add(column.es_index)
            else:
                self.meta.columns.update({
                    "set": {
                        "last_updated": Date.now()
                    },
                    "clear": [
                        "count",
                        "cardinality",
                        "multi",
                        "partitions",
                    ],
                    "where": {"eq": {"names.\\.": ".", "es_index": column.es_index, "es_column": column.es_column}}
                })
                Log.warning("Could not get {{col.es_index}}.{{col.es_column}} info", col=column, cause=e)

    def monitor(self, please_stop):
        please_stop.on_go(lambda: self.todo.add(THREAD_STOP))
        while not please_stop:
            try:
                if not self.todo:
                    old_columns = [
                        c
                        for c in self.meta.columns
                        if (c.last_updated == None or c.last_updated < Date.now()-TOO_OLD) and c.jx_type not in STRUCT
                    ]
                    if old_columns:
                        if DEBUG:
                            Log.note(
                                "Old columns {{names|json}} last updated {{dates|json}}",
                                names=wrap(old_columns).es_column,
                                dates=[Date(t).format() for t in wrap(old_columns).last_updated]
                            )
                        self.todo.extend(old_columns)
                        # TEST CONSISTENCY
                        for c, d in product(list(self.todo.queue), list(self.todo.queue)):
                            if c.es_column == d.es_column and c.es_index == d.es_index and c != d:
                                Log.error("")
                    else:
                        if DEBUG:
                            Log.note("no more metatdata to update")

                column = self.todo.pop(Till(seconds=(10*MINUTE).seconds))
                if column:
                    if column is THREAD_STOP:
                        continue

                    if DEBUG:
                        Log.note("update {{table}}.{{column}}", table=column.es_index, column=column.es_column)
                    if column.es_index in self.index_does_not_exist:
                        self.meta.columns.update({
                            "clear": ".",
                            "where": {"eq": {"es_index": column.es_index}}
                        })
                        continue
                    if column.jx_type in STRUCT or column.es_column.endswith("." + EXISTS_TYPE):
                        column.last_updated = Date.now()
                        continue
                    elif column.last_updated >= Date.now()-TOO_OLD:
                        continue
                    try:
                        self._update_cardinality(column)
                        if DEBUG and not column.es_index.startswith(TEST_TABLE_PREFIX):
                            Log.note("updated {{column.name}}", column=column)
                    except Exception as e:
                        Log.warning("problem getting cardinality for {{column.name}}", column=column, cause=e)
            except Exception as e:
                Log.warning("problem in cardinality monitor", cause=e)

    def not_monitor(self, please_stop):
        Log.alert("metadata scan has been disabled")
        please_stop.on_go(lambda: self.todo.add(THREAD_STOP))
        while not please_stop:
            c = self.todo.pop()
            if c == THREAD_STOP:
                break

            if c.last_updated >= Date.now()-TOO_OLD:
                continue

            self.meta.columns.update({
                "set": {
                    "last_updated": Date.now()
                },
                "clear":[
                    "count",
                    "cardinality",
                    "multi",
                    "partitions",
                ],
                "where": {"eq": {"es_index": c.es_index, "es_column": c.es_column}}
            })
            if DEBUG:
                Log.note("Did not get {{col.es_index}}.{{col.es_column}} info", col=c)

    def get_table(self, alias_name):
        with self.meta.tables.locker:
            return wrap([t for t in self.meta.tables.data if t.name == alias_name])

    def get_snowflake(self, fact_table_name):
        return Snowflake(fact_table_name, self)

    def get_schema(self, name):
        if name == "meta.columns":
            return self.meta.columns.schema
        query_path = split_field(name)
        return self.get_snowflake(query_path[0]).get_schema(join_field(query_path[1:]))


class Snowflake(object):
    """
    REPRESENT ONE ALIAS, AND ITS NESTED ARRAYS
    """

    def __init__(self, alias, namespace):
        self.alias = alias
        self.namespace = namespace


    def get_schema(self, query_path):
        return Schema(query_path, self)

    @property
    def query_paths(self):
        """
        RETURN A LIST OF ALL NESTED COLUMNS
        """
        return self.namespace.alias_to_query_paths[self.alias]

    @property
    def columns(self):
        """
        RETURN ALL COLUMNS FROM ORIGIN OF FACT TABLE
        """
        return self.namespace.get_columns(literal_field(self.alias))


class Schema(jx_base.Schema):
    """
    REPRESENT JUST ONE TABLE IN A SNOWFLAKE
    """

    def __init__(self, query_path, snowflake):
        if not isinstance(snowflake.query_paths[0], list):
            Log.error("Snowflake query paths should be a list of string tuples (well, technically, a list of lists of strings)")
        self.query_path = [
            p
            for p in snowflake.query_paths
            if untype_path(p[0]) == query_path
        ][0]
        self.snowflake = snowflake

    def leaves(self, column_name):
        """
        :param column_name:
        :return: ALL COLUMNS THAT START WITH column_name, NOT INCLUDING DEEPER NESTED COLUMNS
        """
        column_name = unnest_path(column_name)
        columns = self.columns
        deep_path = self.query_path[0]
        for path in self.query_path:
            output = [
                c
                for c in columns
                if (
                    (c.names['.'] != "_id" or column_name == "_id") and
                    c.jx_type not in OBJECTS and
                    startswith_field(unnest_path(c.names[path]), column_name)
                )
            ]
            if output:
                return output
        return []

    def values(self, column_name):
        """
        RETURN ALL COLUMNS THAT column_name REFERES TO
        """
        column_name = unnest_path(column_name)
        columns = self.columns
        deep_path = self.query_path[0]
        for path in self.query_path:
            output = [
                c
                for c in columns
                if (
                    c.jx_type not in STRUCT and
                    untype_path(c.names[path]) == column_name
                )
            ]
            if output:
                return output
        return output

    def __getitem__(self, column_name):
        return self.values(column_name)

    @property
    def name(self):
        return concat_field(self.snowflake.alias, self.query_path[0])

    @property
    def columns(self):
        return self.snowflake.namespace.get_columns(literal_field(self.snowflake.alias))

    def map_to_es(self):
        """
        RETURN A MAP FROM THE NAMESPACE TO THE es_column NAME
        """
        output = {}
        for path in self.query_path:
            set_default(
                output,
                {
                    k: c.es_column
                    for c in self.snowflake.columns
                    if c.jx_type not in STRUCT
                    for rel_name in [c.names[path]]
                    for k in [rel_name, untype_path(rel_name), unnest_path(rel_name)]
                }
            )
        return output


class Table(jx_base.Table):

    def __init__(self, full_name, container):
        jx_base.Table.__init__(self, full_name)
        self.container=container
        self.schema = container.namespace.get_schema(full_name)


def _counting_query(c):
    if c.es_column == "_id":
        return {"filter": {"match_all": {}}}
    elif len(c.nested_path) != 1:
        return {
            "nested": {
                "path": c.nested_path[0]  # FIRST ONE IS LONGEST
            },
            "aggs": {
                "_nested": {"cardinality": {
                    "field": c.es_column,
                    "precision_threshold": 10 if c.es_type in elasticsearch.ES_NUMERIC_TYPES else 100
                }}
            }
        }
    else:
        return {"cardinality": {
            "field": c.es_column
        }}


def metadata_tables():
    return wrap(
        [
            Column(
                names={".": c},
                es_index="meta.tables",
                es_column=c,
                es_type="string",
                nested_path=ROOT_PATH
            )
            for c in [
                "name",
                "url",
                "query_path"
            ]
        ]+[
            Column(
                names={".": c},
                es_index="meta.tables",
                es_column=c,
                es_type="integer",
                nested_path=ROOT_PATH
            )
            for c in [
                "timestamp"
            ]
        ]
    )


OBJECTS = (jx_base.OBJECT, jx_base.EXISTS)