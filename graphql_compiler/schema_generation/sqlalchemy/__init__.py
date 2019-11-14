# Copyright 2019-present Kensho Technologies, LLC.
from ...schema.schema_info import SQLAlchemySchemaInfo
from ..graphql_schema import get_graphql_schema_from_schema_graph
from .edge_descriptors import get_join_descriptors_from_edge_descriptors
from .schema_graph_builder import get_sqlalchemy_schema_graph


def get_sqlalchemy_schema_info(
    vertex_name_to_table, direct_edges, dialect, class_to_field_type_overrides=None
):
    """Return a SQLAlchemySchemaInfo from the metadata.

    Relational databases are supported by compiling to SQLAlchemy core as an intermediate
    language, and then relying on SQLAlchemy's compilation of the dialect-specific SQL string to
    query the target database.

    Constructing the SQLAlchemySchemaInfo class, which contains all the info required to compile
    SQL queries, requires the use of SQLAlchemy Table objects representing underlying SQL
    tables. These can be autogenerated from a SQL database through the reflect() method in a
    SQLAlchemy Metadata object. It is also possible to construct the SQLAlchemy Table objects by
    using the class's init method and specifying the needed metadata. If you choose to use the
    the latter manner, make sure to properly define the optional schema and primary_key fields since
    the compiler relies on these to compile GraphQL to SQL.

    Args:
        vertex_name_to_table: dict, str -> SQLAlchemy Table. This dictionary is used to generate the
                              GraphQL objects in the schema in the SQLAlchemySchemaInfo. Each
                              SQLAlchemyTable will be represented as a GraphQL object. The GraphQL
                              object names are the dictionary keys. The fields of the GraphQL
                              objects will be inferred from the columns of the underlying tables.
                              The fields will have the same name as the underlying columns and
                              columns with unsupported types, (SQL types with no matching GraphQL
                              type), will be ignored.
        direct_edges: dict, str-> DirectEdgeDescriptor. The traversal of a direct
                      edge gets compiled to a SQL join in graphql_to_sql(). Therefore, each
                      DirectEdgeDescriptor not only specifies the source and destination GraphQL
                      objects, but also which columns to use to use when generating a SQL join
                      between the underlying source and destination tables. The names of the edges
                      are the keys in the dictionary and the edges will be rendered as vertex fields
                      named out_<edgeName> and in_<edgeName> in the source and destination GraphQL
                      objects respectively. The direct edge names must not conflict with the GraphQL
                      object names.
        dialect: sqlalchemy.engine.interfaces.Dialect, specifying the dialect we are compiling to
                 (e.g. sqlalchemy.dialects.mssql.dialect()).
        class_to_field_type_overrides: optional dict, class name -> {field name -> field type},
                                       (string -> {string -> GraphQLType}). Used to override the
                                       type of a field in the class where it's first defined and all
                                       the class's subclasses.
    Return:
        SQLAlchemySchemaInfo containing the full information needed to compile SQL queries.
    """
    schema_graph = get_sqlalchemy_schema_graph(vertex_name_to_table, direct_edges)

    graphql_schema, type_equivalence_hints = get_graphql_schema_from_schema_graph(
        schema_graph, class_to_field_type_overrides=class_to_field_type_overrides,
        hidden_classes=set()
    )

    join_descriptors = get_join_descriptors_from_edge_descriptors(direct_edges)

    return SQLAlchemySchemaInfo(
        graphql_schema, type_equivalence_hints, dialect, vertex_name_to_table, join_descriptors)
