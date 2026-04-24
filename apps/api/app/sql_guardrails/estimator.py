from __future__ import annotations

import sqlglot
from sqlglot import exp


class SQLComplexityEstimator:
    def estimate(self, sql: str) -> int:
        parsed = sqlglot.parse_one(sql, read="postgres")
        joins = len(list(parsed.find_all(exp.Join)))
        aggregations = len(list(parsed.find_all(exp.AggFunc)))
        group_bys = len(list(parsed.find_all(exp.Group)))
        where_clauses = len(list(parsed.find_all(exp.Where)))
        subqueries = len(list(parsed.find_all(exp.Subquery)))
        return joins * 2 + aggregations + group_bys + where_clauses + subqueries * 3


complexity_estimator = SQLComplexityEstimator()

