import unittest

from app.sql_guardrails.validator import sql_validator


class TestSQLGuardrails(unittest.TestCase):
    def test_guardrails_allow_safe_select_query(self) -> None:
        sql = (
            "SELECT DATE(ot.order_timestamp) AS order_date, "
            "COUNT(DISTINCT ot.order_id) AS total_orders "
            "FROM analytics.order_tender_facts ot "
            "WHERE ot.order_timestamp >= :start_date AND ot.order_timestamp < :end_date "
            "GROUP BY DATE(ot.order_timestamp) "
            "ORDER BY order_date "
            "LIMIT :row_limit"
        )
        result = sql_validator.validate(sql, row_limit=50, dataset_key="order_tender_facts", dialect="postgres")
        self.assertTrue(result.allowed)
        self.assertEqual(result.blocked_reasons, [])
        self.assertGreaterEqual(result.complexity_score, 1)

    def test_guardrails_block_dangerous_query(self) -> None:
        sql = "DROP TABLE analytics.order_tender_facts"
        result = sql_validator.validate(sql, row_limit=50, dataset_key="order_tender_facts", dialect="postgres")
        self.assertFalse(result.allowed)
        self.assertTrue(any("DDL/DML" in reason or "SELECT" in reason for reason in result.blocked_reasons))


if __name__ == "__main__":
    unittest.main()
