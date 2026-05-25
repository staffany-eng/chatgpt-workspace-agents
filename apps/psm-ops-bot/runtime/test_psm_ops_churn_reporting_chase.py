from __future__ import annotations

import importlib.util
import os
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo


SCRIPT_PATH = Path(__file__).parent / "scripts" / "psm_ops_churn_reporting_chase.py"


def load_script():
    spec = importlib.util.spec_from_file_location("psm_ops_churn_reporting_chase", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class PsmOpsChurnReportingChaseScriptTest(unittest.TestCase):
    def setUp(self):
        self.module = load_script()
        self.as_of = datetime(2026, 5, 25, 9, 0, tzinfo=ZoneInfo("Asia/Singapore"))
        self.env = patch.dict(
            os.environ,
            {
                "PSM_OPS_CHURN_REPORTING_CHANNEL_ID": "C019RVCR4S1",
                "PSM_OPS_CHURN_REPORTING_BQ_PROJECT": "staffany-warehouse",
                "PSM_OPS_CHURN_REPORTING_BQ_DATASET": "analytics",
            },
            clear=False,
        )
        self.env.start()
        self.addCleanup(self.env.stop)

    def dashboard_row(self, **overrides):
        row = {
            "company_id": "100",
            "raw_company_id": "100",
            "company_name": "Big Eats",
            "deal_psm_name": "Will",
            "renewal_quarter": "26Q2",
            "renewal_date": "2026-06-01",
            "churn_class": "4-Non-Actualized (Red)",
            "renewal_assessment": "Will Not Renew",
            "renewal_assessment_reason": "Low value realization",
            "company_churn_reason": "Too expensive",
            "company_churn_reason_bucket": "Pricing",
            "company_mrr": 4200,
            "weighted_churn_mrr": 840,
            "last_main_paid_deal_url": "https://app.hubspot.com/contacts/4137076/record/0-3/123",
        }
        row.update(overrides)
        return row

    def upcoming_row(self, **overrides):
        row = {
            "canonical_company_id": "200",
            "raw_company_id": "200",
            "company_name": "B Bistro",
            "deal_psm_name": "Josica",
            "renewal_quarter": "26Q2",
            "renewal_date": "2026-05-15",
            "renewal_bucket": "At Risk",
            "renewal_progress_status": "Overdue",
            "renewal_assessment": "Will Renew",
            "renewal_assessment_reason": "",
            "deal_stage": "Renewal",
            "deal_billing_status": "Unpaid",
            "current_mrr": 500,
        }
        row.update(overrides)
        return row

    def test_reporting_window_current_plus_next_two_quarters(self):
        window = self.module.reporting_window(self.as_of)

        self.assertEqual(window["start"].isoformat(), "2026-04-01")
        self.assertEqual(window["end"].isoformat(), "2027-01-01")
        self.assertEqual(window["quarters"], ["26Q2", "26Q3", "26Q4"])

    def test_dashboard_292_query_uses_repo_sql_and_window(self):
        query = self.module.build_dashboard_292_query(self.as_of)

        self.assertIn("get_churn_class", query)
        self.assertIn("churn_class IS NOT NULL", query)
        self.assertIn("DATE '2026-04-01'", query)
        self.assertIn("DATE '2027-01-01'", query)
        self.assertIn("`staffany-warehouse.analytics.fct_alldealsmrr`", query)
        self.assertNotIn("13UjJOZpkyngN_5oo4LtzeJWfqhc7PAD8hR1E_" + "aU6gP0", query)

    def test_upcoming_query_uses_fixed_bigquery_sources_and_window(self):
        query = self.module.build_upcoming_query(self.as_of)

        self.assertIn("`staffany-warehouse.analytics.fct_upcoming_renewal_cycles`", query)
        self.assertIn("`staffany-warehouse.analytics.fct_company_revenue_snapshot`", query)
        self.assertIn("`staffany-warehouse.analytics.fct_churnmrrbymonth`", query)
        self.assertIn("DATE '2026-04-01'", query)
        self.assertIn("DATE '2027-01-01'", query)
        self.assertNotIn("spreadsheets" + ".values", query)

    def test_dashboard_actualized_requires_company_churn_reason_and_bucket(self):
        row = self.dashboard_row(
            churn_class="1-Actualized",
            company_churn_reason="",
            company_churn_reason_bucket=None,
            renewal_assessment="Will Renew",
            renewal_assessment_reason="Has reason",
        )

        self.assertTrue(self.module.dashboard_needs_chase(row))
        self.assertIn("company churn reason missing", self.module.dashboard_chase_reason(row))
        self.assertIn("company churn reason bucket missing", self.module.dashboard_chase_reason(row))
        self.assertNotIn("renewal assessment reason missing", self.module.dashboard_chase_reason(row))

    def test_dashboard_non_actualized_requires_renewal_assessment_and_reason(self):
        row = self.dashboard_row(
            churn_class="5-Non-Actualized (Orange)",
            renewal_assessment="",
            renewal_assessment_reason="TBD",
            company_churn_reason="",
            company_churn_reason_bucket="",
        )

        self.assertTrue(self.module.dashboard_needs_chase(row))
        self.assertIn("renewal assessment missing", self.module.dashboard_chase_reason(row))
        self.assertIn("renewal assessment reason missing", self.module.dashboard_chase_reason(row))
        self.assertNotIn("company churn reason missing", self.module.dashboard_chase_reason(row))

    def test_dashboard_ignores_null_churn_class(self):
        row = self.dashboard_row(churn_class=None, renewal_assessment=None)

        self.assertFalse(self.module.dashboard_needs_chase(row))

    def test_missing_owner_surfaces_in_dashboard_section(self):
        row = self.dashboard_row(deal_psm_name="", renewal_assessment="Will Not Renew", renewal_assessment_reason="Budget")

        self.assertTrue(self.module.dashboard_needs_chase(row))
        self.assertIn("ask who owns this account", self.module.dashboard_chase_reason(row))

    def test_upcoming_exception_only_for_risky_rows_not_in_dashboard_292(self):
        dashboard_rows = [self.dashboard_row(company_id="200", raw_company_id="raw-200")]
        dashboard_keys = self.module.dashboard_company_keys(dashboard_rows)
        duplicate = self.upcoming_row(canonical_company_id="200", raw_company_id="other")
        exception = self.upcoming_row(canonical_company_id="201", raw_company_id="raw-201", renewal_progress_status="No renewal deal yet")
        ordinary = self.upcoming_row(
            canonical_company_id="202",
            raw_company_id="raw-202",
            renewal_bucket="Renewed Paid",
            renewal_progress_status="Paid",
            deal_billing_status="Paid",
        )

        self.assertFalse(self.module.upcoming_needs_chase(duplicate, dashboard_keys))
        self.assertTrue(self.module.upcoming_needs_chase(exception, dashboard_keys))
        self.assertFalse(self.module.upcoming_needs_chase(ordinary, dashboard_keys))

    def test_owner_missing_group_and_row_level_formatting(self):
        rows = {
            "dashboard_rows": [
                self.dashboard_row(
                    company_name="A Food",
                    deal_psm_name="",
                    churn_class="1-Actualized",
                    company_churn_reason="",
                    company_churn_reason_bucket="",
                )
            ],
            "upcoming_rows": [
                self.upcoming_row(
                    canonical_company_id="300",
                    raw_company_id="raw-300",
                    company_name="B Bistro",
                    deal_psm_name="",
                    renewal_progress_status="Overdue",
                )
            ],
        }

        result = self.module.build_result(rows, self.as_of, dry_run=True, max_rows=5)
        output = self.module.format_result(result)

        self.assertEqual(result["dashboard_owner_missing"], 1)
        self.assertEqual(result["upcoming_owner_missing"], 1)
        self.assertTrue(output.startswith("PSM Ops automation: Weekly churn reporting chase DRY RUN"))
        self.assertIn("*Dashboard 292 churn-risk chase*", output)
        self.assertIn("*Upcoming renewal exceptions*", output)
        self.assertIn("Owner missing (1)", output)
        self.assertIn("A Food", output)
        self.assertIn("B Bistro", output)
        self.assertIn("who owns the account", output)

    def test_max_row_cap_is_per_section(self):
        rows = {
            "dashboard_rows": [
                self.dashboard_row(company_id="101", raw_company_id="101", company_name="A", churn_class="1-Actualized", company_churn_reason="", company_churn_reason_bucket=""),
                self.dashboard_row(company_id="102", raw_company_id="102", company_name="B", churn_class="1-Actualized", company_churn_reason="", company_churn_reason_bucket=""),
            ],
            "upcoming_rows": [
                self.upcoming_row(canonical_company_id="201", raw_company_id="201", company_name="C"),
                self.upcoming_row(canonical_company_id="202", raw_company_id="202", company_name="D"),
            ],
        }

        output = self.module.format_result(self.module.build_result(rows, self.as_of, True, 1))

        self.assertIn("...and 1 more Dashboard 292 rows", output)
        self.assertIn("...and 1 more upcoming rows", output)

    def test_silent_when_no_cleanup_rows(self):
        rows = {
            "dashboard_rows": [self.dashboard_row()],
            "upcoming_rows": [self.upcoming_row(renewal_bucket="Renewed Paid", renewal_progress_status="Paid", deal_billing_status="Paid")],
        }

        output = self.module.format_result(self.module.build_result(rows, self.as_of, False, 10))

        self.assertTrue(output.startswith("[SILENT] PSM Ops automation:"))
        self.assertIn("26Q2, 26Q3, 26Q4", output)

    def test_invalid_bigquery_identifier_is_rejected(self):
        with self.assertRaises(self.module.ChurnReportingError):
            self.module.build_upcoming_query(self.as_of, project="staffany-warehouse; DROP TABLE x", dataset="analytics")


if __name__ == "__main__":
    unittest.main()
