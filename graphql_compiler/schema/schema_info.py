# Copyright 2019-present Kensho Technologies, LLC.
from abc import ABCMeta
from collections import namedtuple
from dataclasses import dataclass, field
from enum import Enum, auto, unique
from functools import partial
from typing import Dict, Optional, Set

from graphql.type import GraphQLSchema
from graphql.type.definition import GraphQLInterfaceType, GraphQLObjectType
import six
import sqlalchemy
from sqlalchemy.dialects.mssql import dialect as mssql_dialect
from sqlalchemy.dialects.mysql import dialect as mysql_dialect
from sqlalchemy.dialects.postgresql import dialect as postgresql_dialect
from sqlalchemy.engine.interfaces import Dialect

from . import TypeEquivalenceHintsType, is_vertex_field_name
from ..cost_estimation.statistics import Statistics
from ..schema_generation.schema_graph import SchemaGraph


# Describes the intent to join two tables using the specified columns.
#
# The resulting join expression could be something like:
# JOIN origin_table.from_column = destination_table.to_column
#
# The type of join (inner vs left, etc.) is not specified.
# The tables are not specified.
DirectJoinDescriptor = namedtuple(
    "DirectJoinDescriptor",
    (
        "from_column",  # The column in the source table we intend to join on.
        "to_column",  # The column in the destination table we intend to join on.
    ),
)


@dataclass
class GenericSchemaInfo:
    """Class for storing generic schema info required for querying."""

    schema: GraphQLSchema

    # Optional dict of GraphQL interface or type -> GraphQL union.
    # Used as a workaround for GraphQL's lack of support for
    # inheritance across "types" (i.e. non-interfaces), as well as a
    # workaround for Gremlin's total lack of inheritance-awareness.
    # The key-value pairs in the dict specify that the "key" type
    # is equivalent to the "value" type, i.e. that the GraphQL type or
    # interface in the key is the most-derived common supertype
    # of every GraphQL type in the "value" GraphQL union.
    # Recursive expansion of type equivalence hints is not performed,
    # and only type-level correctness of this argument is enforced.
    # See README.md for more details on everything this parameter does.
    # *****
    # Be very careful with this option, as bad input here will
    # lead to incorrect output queries being generated.
    # *****
    # TODO: make sure we are treating empty dict the same as None
    type_equivalence_hints: Optional[Dict[str, str]]


@dataclass
class BackendSpecificSchemaInfo(metaclass=ABCMeta):
    """Common base class to be used by all backend-specific schema info classes.

    This helps hide that the data actually lives one nesting level deeper.
    """

    generic_schema_info: GenericSchemaInfo

    @property
    def schema(self) -> GraphQLSchema:
        """Return schema."""
        return self.generic_schema_info.schema

    @property
    def type_equivalence_hints(self) -> Optional[Dict[str, str]]:
        """Return type equivalence hints."""
        return self.generic_schema_info.type_equivalence_hints


@dataclass
class MatchSchemaInfo(BackendSpecificSchemaInfo):
    pass


def create_match_schema_info(
    schema: GraphQLSchema, type_equivalence_hints: Optional[Dict[str, str]] = None
) -> MatchSchemaInfo:
    """Create a SchemaInfo object for a database using MATCH."""
    generic_schema_info = GenericSchemaInfo(
        schema=schema, type_equivalence_hints=type_equivalence_hints
    )
    return MatchSchemaInfo(generic_schema_info=generic_schema_info)


@dataclass
class GremlinSchemaInfo(BackendSpecificSchemaInfo):
    pass


def create_gremlin_schema_info(
    schema: GraphQLSchema, type_equivalence_hints: Optional[Dict[str, str]] = None
) -> GremlinSchemaInfo:
    """Create a SchemaInfo object for a database using Gremlin."""
    generic_schema_info = GenericSchemaInfo(
        schema=schema, type_equivalence_hints=type_equivalence_hints
    )
    return GremlinSchemaInfo(generic_schema_info=generic_schema_info)


@dataclass
class CypherSchemaInfo(BackendSpecificSchemaInfo):
    pass


def create_cypher_schema_info(
    schema: GraphQLSchema, type_equivalence_hints: Optional[Dict[str, str]] = None
) -> CypherSchemaInfo:
    """Create a SchemaInfo object for a database using Cypher."""
    generic_schema_info = GenericSchemaInfo(
        schema=schema, type_equivalence_hints=type_equivalence_hints
    )
    return CypherSchemaInfo(generic_schema_info=generic_schema_info)


@dataclass
class SQLSchemaInfo(BackendSpecificSchemaInfo):
    """Schema information specific to SQL databases.

    If the flavors start diverging in their attributes, consider making a class per flavor.
    """

    # Specifying the dialect for which we are compiling
    # e.g. sqlalchemy.dialects.mssql.dialect()
    dialect: Dialect
    # dict mapping every GraphQL object type or interface type name in the schema to
    # a sqlalchemy table.
    # Column types that do not exist for this dialect are not allowed.
    # All tables are expected to have primary keys.

    vertex_name_to_table: Dict[str, sqlalchemy.Table]
    # dict mapping every GraphQL object type or interface type name in the schema to
    # dict mapping every vertex field name at that type to a DirectJoinDescriptor.
    # The tables the join is to be performed on are not specified.
    # They are inferred from the schema and the tables dictionary.
    join_descriptors: Dict[str, Dict[str, DirectJoinDescriptor]]


def _create_sql_schema_info(
    dialect: Dialect,
    schema: GraphQLSchema,
    vertex_name_to_table: Dict[str, sqlalchemy.Table],
    join_descriptors: Dict[str, Dict[str, DirectJoinDescriptor]],
    type_equivalence_hints: Optional[Dict[str, str]] = None,
) -> SQLSchemaInfo:
    """Create a SQLSchemaInfo object for a database using a flavor of SQL."""
    generic_schema_info = GenericSchemaInfo(
        schema=schema, type_equivalence_hints=type_equivalence_hints
    )

    return SQLSchemaInfo(
        generic_schema_info=generic_schema_info,
        dialect=dialect,
        vertex_name_to_table=vertex_name_to_table,
        join_descriptors=join_descriptors,
    )


create_postgresql_schema_info = partial(_create_sql_schema_info, postgresql_dialect)
create_mssql_schema_info = partial(_create_sql_schema_info, mssql_dialect)
create_mysql_schema_info = partial(_create_sql_schema_info, mysql_dialect)


# Complete schema information sufficient to compile GraphQL queries for most backends
CommonSchemaInfo = namedtuple(
    "CommonSchemaInfo",
    (
        # GraphQLSchema
        "schema",
        # optional dict of GraphQL interface or type -> GraphQL union.
        # Used as a workaround for GraphQL's lack of support for
        # inheritance across "types" (i.e. non-interfaces), as well as a
        # workaround for Gremlin's total lack of inheritance-awareness.
        # The key-value pairs in the dict specify that the "key" type
        # is equivalent to the "value" type, i.e. that the GraphQL type or
        # interface in the key is the most-derived common supertype
        # of every GraphQL type in the "value" GraphQL union.
        # Recursive expansion of type equivalence hints is not performed,
        # and only type-level correctness of this argument is enforced.
        # See README.md for more details on everything this parameter does.
        # *****
        # Be very careful with this option, as bad input here will
        # lead to incorrect output queries being generated.
        # *****
        "type_equivalence_hints",
    ),
)


# Complete schema information sufficient to compile GraphQL queries to SQLAlchemy
#
# It describes the tables that correspond to each type (object type or interface type),
# and gives instructions on how to perform joins for each vertex field. The property fields on each
# type are implicitly mapped to columns with the same name on the corresponding table.
#
# NOTES:
# - RootSchemaQuery is a special type that does not need a corresponding table.
# - Builtin types like __Schema, __Type, etc. don't need corresponding tables.
# - Builtin fields like _x_count do not need corresponding columns.
SQLAlchemySchemaInfo = namedtuple(
    "SQLAlchemySchemaInfo",
    (
        # GraphQLSchema
        "schema",
        # optional dict of GraphQL interface or type -> GraphQL union.
        # Used as a workaround for GraphQL's lack of support for
        # inheritance across "types" (i.e. non-interfaces), as well as a
        # workaround for Gremlin's total lack of inheritance-awareness.
        # The key-value pairs in the dict specify that the "key" type
        # is equivalent to the "value" type, i.e. that the GraphQL type or
        # interface in the key is the most-derived common supertype
        # of every GraphQL type in the "value" GraphQL union.
        # Recursive expansion of type equivalence hints is not performed,
        # and only type-level correctness of this argument is enforced.
        # See README.md for more details on everything this parameter does.
        # *****
        # Be very careful with this option, as bad input here will
        # lead to incorrect output queries being generated.
        # *****
        "type_equivalence_hints",
        # sqlalchemy.engine.interfaces.Dialect, specifying the dialect we are compiling for
        # (e.g. sqlalchemy.dialects.mssql.dialect()).
        "dialect",
        # dict mapping every graphql object type or interface type name in the schema to
        # a sqlalchemy table. Column types that do not exist for this dialect are not allowed.
        # All tables are expected to have primary keys.
        "vertex_name_to_table",
        # dict mapping every graphql object type or interface type name in the schema to:
        #    dict mapping every vertex field name at that type to a DirectJoinDescriptor. The
        #    tables the join is to be performed on are not specified. They are inferred from
        #    the schema and the tables dictionary.
        "join_descriptors",
    ),
)


def make_sqlalchemy_schema_info(
    schema, type_equivalence_hints, dialect, vertex_name_to_table, join_descriptors, validate=True
):
    """Make a SQLAlchemySchemaInfo if the input provided is valid.

    See the documentation of SQLAlchemyschemaInfo for more detailed documentation of the args.

    Args:
        schema: GraphQLSchema
        type_equivalence_hints: optional dict of GraphQL interface or type -> GraphQL union.
                                Used as a workaround for GraphQL's lack of support for
                                inheritance across "types" (i.e. non-interfaces), as well as a
                                workaround for Gremlin's total lack of inheritance-awareness.
                                The key-value pairs in the dict specify that the "key" type
                                is equivalent to the "value" type, i.e. that the GraphQL type or
                                interface in the key is the most-derived common supertype
                                of every GraphQL type in the "value" GraphQL union.
                                Recursive expansion of type equivalence hints is not performed,
                                and only type-level correctness of this argument is enforced.
                                See README.md for more details on everything this parameter does.
                                *****
                                Be very careful with this option, as bad input here will
                                lead to incorrect output queries being generated.
                                *****
        dialect: sqlalchemy.engine.interfaces.Dialect
        vertex_name_to_table: dict mapping every graphql object type or interface type name in the
                              schema to a sqlalchemy table
        join_descriptors: dict mapping graphql object and interface type names in the schema to:
                             dict mapping every vertex field name at that type to a
                             DirectJoinDescriptor. The tables the join is to be performed on are not
                             specified. They are inferred from the schema and the tables dictionary.
        validate: Optional bool (default True), specifying whether to validate that the given
                  input is valid for creation of a SQLAlchemySchemaInfo. Consider not validating
                  to save on performance when dealing with a large schema.

    Returns:
        SQLAlchemySchemaInfo containing the input arguments provided
    """
    if validate:
        types_to_map = (GraphQLInterfaceType, GraphQLObjectType)
        builtin_fields = {
            "_x_count",
        }
        # TODO(bojanserafimov): More validation can be done:
        # - are the types of the columns compatible with the GraphQL type of the property field?
        # - do joins join on columns on which the (=) operator makes sense?
        # - do inherited columns have exactly the same type on the parent and child table?
        # - are all the column types available in this dialect?
        for type_name, graphql_type in six.iteritems(schema.type_map):
            if isinstance(graphql_type, types_to_map):
                if type_name != "RootSchemaQuery" and not type_name.startswith("__"):
                    # Check existence of sqlalchemy table for this type
                    if type_name not in vertex_name_to_table:
                        raise AssertionError(u"Table for type {} not found".format(type_name))
                    table = vertex_name_to_table[type_name]
                    if not isinstance(table, sqlalchemy.Table):
                        raise AssertionError(
                            u"Table for type {} has wrong type {}".format(type_name, type(table))
                        )

                    # Check existence of all fields
                    for field_name in six.iterkeys(graphql_type.fields):
                        if is_vertex_field_name(field_name):
                            if field_name not in join_descriptors.get(type_name, {}):
                                raise AssertionError(
                                    u"No join descriptor was specified for vertex "
                                    u"field {} on type {}".format(field_name, type_name)
                                )
                        else:
                            if field_name not in builtin_fields and field_name not in table.c:
                                raise AssertionError(
                                    u"Table for type {} has no column "
                                    u"for property field {}".format(type_name, field_name)
                                )

    return SQLAlchemySchemaInfo(
        schema, type_equivalence_hints, dialect, vertex_name_to_table, join_descriptors
    )


@unique
class EdgeConstraint(Enum):
    """An integrity constraint on a directed edge in the schema."""

    AtLeastOneSource = auto()
    AtMostOneSource = auto()
    AtLeastOneDestination = auto()
    AtMostOneDestination = auto()


@dataclass
class QueryPlanningSchemaInfo:
    """All schema information sufficient for query cost estimation and auto pagination."""

    # The schema used for querying
    schema: GraphQLSchema

    # optional dict of GraphQL interface or type -> GraphQL union.
    # Used as a workaround for GraphQL's lack of support for
    # inheritance across "types" (i.e. non-interfaces), as well as a
    # workaround for Gremlin's total lack of inheritance-awareness.
    # The key-value pairs in the dict specify that the "key" type
    # is equivalent to the "value" type, i.e. that the GraphQL type or
    # interface in the key is the most-derived common supertype
    # of every GraphQL type in the "value" GraphQL union.
    # Recursive expansion of type equivalence hints is not performed,
    # and only type-level correctness of this argument is enforced.
    # See README.md for more details on everything this parameter does.
    # *****
    # Be very careful with this option, as bad input here will
    # lead to incorrect output queries being generated.
    # *****
    type_equivalence_hints: TypeEquivalenceHintsType

    # A SchemaGraph instance that corresponds to the GraphQLSchema, containing additional
    # information on unique indexes, subclass sets, and edge base connection classes.
    schema_graph: SchemaGraph

    # A Statistics object giving statistical information about all objects in the schema.
    statistics: Statistics

    # Dict mapping vertex names in the graphql schema to the Int or ID type property name
    # to be used for pagination on that vertex. This property should be non-null and
    # unique for all rows.  An easy choice for pagination key in most situations is the
    # primary key. The pagination key for a vertex can be omitted making the vertex
    # ineligible for pagination.
    #
    # NOTE(bojanserafimov): The type of this property might be different in the
    #                       schema graph, due to the process of type overrides that happens
    #                       during schema generation.
    pagination_keys: Dict[str, str]

    # Dict mapping vertex names in the graphql schema to a set of property names that
    # are known to contain uniformly distributed uppercase uuid values. The types of those
    # fields are expected to be ID or String.
    uuid4_fields: Dict[str, Set[str]]

    # Map edge names to constraints inferred for them.
    edge_constraints: Dict[str, Set[EdgeConstraint]] = field(default_factory=dict)
