# Copyright 2019-present Kensho Technologies, LLC.
import unittest

import pytest

from ...ast_manipulation import safe_parse_graphql
from ...cost_estimation.statistics import LocalStatistics
from ...query_pagination import QueryAndParameters, paginate_query
from ..test_helpers import generate_schema_graph


# The following TestCase class uses the 'snapshot_orientdb_client' fixture
# which pylint does not recognize as a class member.
# pylint: disable=no-member
@pytest.mark.slow
class QueryPaginationTests(unittest.TestCase):
    """Test the cost estimation module using standard input data when possible."""

    # TODO: These tests can be sped up by having an existing test SchemaGraph object.
    @pytest.mark.usefixtures('snapshot_orientdb_client')
    def test_basic_pagination(self):
        """"Ensure we correctly estimate the cardinality of the query root."""
        schema_graph = generate_schema_graph(self.orientdb_client)
        test_data = '''{
            Animal {
                name @output(out_name: "animal")
            }
        }'''
        test_ast = safe_parse_graphql(test_data)
        parameters = {}

        count_data = {
            'Animal': 4,
        }

        statistics = LocalStatistics(count_data)

        # Since query pagination is still a skeleton, we expect a NotImplementedError for this test.
        # Once query pagination is implemented, the result of this call should be equal to
        # expected_query_list.
        # pylint: disable=unused-variable
        with self.assertRaises(NotImplementedError):
            paginated_queries = paginate_query(                     # noqa: unused-variable
                schema_graph, statistics, test_ast, parameters, 1
            )

        expected_query_list = (                                     # noqa: unused-variable
            QueryAndParameters(
                '''{
                    Animal {
                        uuid @filter(op_name: "<", value: ["$_paged_upper_param_on_Animal_uuid"])
                        name @output(out_name: "animal")
                    }
                }''',
                {
                    '_paged_upper_param_on_Animal_uuid': '40000000-0000-0000-0000-000000000000',
                }
            ),
            QueryAndParameters(
                '''{
                    Animal {
                        uuid @filter(op_name: ">=", value: ["$_paged_lower_param_on_Animal_uuid"])
                        name @output(out_name: "animal")
                    }
                }''',
                {
                    '_paged_lower_param_on_Animal_uuid': '40000000-0000-0000-0000-000000000000',
                }
            )
        )
        # pylint: enable=unused-variable
