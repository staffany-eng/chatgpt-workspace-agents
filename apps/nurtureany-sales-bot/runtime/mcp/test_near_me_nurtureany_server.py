import importlib.util
import os
import sys
import types
import unittest
from pathlib import Path

MCP_DIR = Path(__file__).resolve().parent
if str(MCP_DIR) not in sys.path:
    sys.path.insert(0, str(MCP_DIR))
from unittest.mock import patch


class FakeMCP:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def tool(self):
        def decorate(func):
            return func

        return decorate

    def run(self, *args, **kwargs):
        return None


def load_near_me_module():
    sys.modules["mcp"] = types.ModuleType("mcp")
    sys.modules["mcp.server"] = types.ModuleType("mcp.server")
    fastmcp = types.ModuleType("mcp.server.fastmcp")
    fastmcp.FastMCP = FakeMCP
    sys.modules["mcp.server.fastmcp"] = fastmcp

    module_name = "near_me_nurtureany_server_under_test"
    sys.modules.pop(module_name, None)
    path = Path(__file__).with_name("near_me_nurtureany_server.py")
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class NearMeNurtureAnyServerTest(unittest.TestCase):
    def setUp(self):
        self.module = load_near_me_module()
        self.env_patch = patch.dict(
            os.environ,
            {
                "NURTUREANY_C360_COMPANY_URL_TEMPLATE": "",
                "NURTUREANY_C360_ORG_URL_TEMPLATE": "",
                "NURTUREANY_C360_ROUTE_KEY_BY_COMPANY_ID": "",
            },
        )
        self.env_patch.start()

    def tearDown(self):
        self.env_patch.stop()

    def known_area(self, area_id="sg_raffles_place"):
        return self.module._area_public(self.module._known_area_by_id(area_id))

    def test_raffles_place_alias_snaps_to_known_area(self):
        result = self.module.resolve_known_area_for_near_me(
            "kaiyi@staffany.com",
            location_text="test with Raffles Place",
        )

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(result["answer"]["area_id"], "sg_raffles_place")
        self.assertEqual(result["answer"]["snap_status"], "matched_by_alias")

    def test_c360_query_uses_geofence_sections_and_live_customer_layer(self):
        result = self.module.build_near_me_c360_customer_query(
            "kaiyi@staffany.com",
            area_id="sg_raffles_place",
        )
        sql = result["answer"]["sql"]

        self.assertEqual(result["answer"]["known_area"]["area_id"], "sg_raffles_place")
        self.assertIn("`staffany-warehouse.kraken_rds.Locations`", sql)
        self.assertIn("`staffany-warehouse.analytics.dim_sections`", sql)
        self.assertIn("`staffany-warehouse.analytics.dim_org_section`", sql)
        self.assertIn("`staffany-warehouse.analytics.fct_deal_org_company`", sql)
        self.assertIn("LEFT JOIN `staffany-warehouse.analytics.fct_company_org_mrr`", sql)
        self.assertIn("COALESCE(ds.isarchived, FALSE) = FALSE", sql)
        self.assertIn("ABS(raw_latitude) > 90", sql)
        self.assertNotIn("ClockRecords", sql)
        self.assertNotIn("CicoGeoData", sql)
        self.assertNotIn("employee", sql.lower())

    def test_outlet_matches_query_uses_bigquery_memory_table(self):
        with patch.dict(
            os.environ,
            {"NURTUREANY_OUTLET_MATCHES_TABLE": "staffany-warehouse.analytics.nurtureany_near_me_outlet_matches"},
        ):
            result = self.module.build_near_me_outlet_matches_query(
                "kaiyi@staffany.com",
                area_id="sg_raffles_place",
                limit=500,
            )
        sql = result["answer"]["sql"]

        self.assertEqual(result["answer"]["known_area"]["area_id"], "sg_raffles_place")
        self.assertEqual(result["answer"]["execute_with"], "staffany_bigquery.execute_sql_readonly")
        self.assertIn("`staffany-warehouse.analytics.nurtureany_near_me_outlet_matches`", sql)
        self.assertIn("LOWER(COALESCE(match_status, 'candidate')) != 'rejected'", sql)
        self.assertIn("hubspot_company_id", sql)
        self.assertIn("organisation_id", sql)
        self.assertIn("LIMIT 100", sql)
        self.assertIn("BigQuery outlet_matches is the memory layer", sql)

    def test_google_places_refresh_uses_known_area_center_and_live_candidates(self):
        calls = []

        def fake_request(body):
            calls.append(body)
            return {
                "places": [
                    {
                        "id": "place-1",
                        "displayName": {"text": "Example Bistro"},
                        "formattedAddress": "1 Raffles Place, Singapore",
                        "location": {"latitude": 1.284, "longitude": 103.852},
                        "googleMapsUri": "https://maps.google.com/?cid=1",
                    }
                ]
            }

        with patch.dict(os.environ, {"GOOGLE_PLACES_API_KEY": "test-key"}), patch.object(
            self.module, "_request_google_places", side_effect=fake_request
        ):
            result = self.module.refresh_google_places_for_known_area(
                "kaiyi@staffany.com",
                "sg_raffles_place",
                max_results=50,
            )

        self.assertEqual(len(calls), 1)
        request = calls[0]
        circle = request["locationRestriction"]["circle"]
        self.assertEqual(request["includedTypes"], ["restaurant"])
        self.assertEqual(request["maxResultCount"], self.module.MAX_GOOGLE_PLACES_RESULTS)
        self.assertEqual(circle["center"]["latitude"], self.known_area()["latitude"])
        self.assertEqual(circle["center"]["longitude"], self.known_area()["longitude"])
        self.assertEqual(circle["radius"], float(self.known_area()["radius_m"]))
        place = result["answer"]["places"][0]
        self.assertEqual(place["match_status"], "candidate")
        self.assertEqual(place["store_policy"], "live_candidate_only_until_review_approval")

    def test_vivocity_keeps_multiple_outlets_under_one_company(self):
        outlets = [
            {
                "outlet_location_id": "outlet-1",
                "outlet_name": "Acme Kitchen VivoCity",
                "google_place_id": "place-1",
                "hubspot_company_id": "company-1",
                "organisation_id": "org-1",
                "match_status": "confirmed",
                "account_status": "customer",
                "company": {"company_name": "Acme Group", "hubspot_company_id": "company-1"},
            },
            {
                "outlet_location_id": "outlet-2",
                "outlet_name": "Acme Express VivoCity",
                "google_place_id": "place-2",
                "hubspot_company_id": "company-1",
                "organisation_id": "org-1",
                "match_status": "confirmed",
                "account_status": "customer",
                "company": {"company_name": "Acme Group", "hubspot_company_id": "company-1"},
            },
        ]

        result = self.module.merge_near_me_sources(
            "kaiyi@staffany.com",
            self.known_area("sg_vivocity"),
            outlet_matches=outlets,
            c360_customer_rows=[],
            google_places=[],
        )

        customers = result["answer"]["customers_nearby"]
        self.assertEqual(len(customers), 1)
        self.assertEqual(customers[0]["hubspot_company_id"], "company-1")
        self.assertEqual(len(customers[0]["outlet_locations"]), 2)

    def test_current_c360_customer_appears_without_outlet_location(self):
        result = self.module.merge_near_me_sources(
            "kaiyi@staffany.com",
            self.known_area("sg_raffles_place"),
            outlet_matches=[],
            c360_customer_rows=[
                {
                    "organisation_id": "org-c360",
                    "hubspot_company_id": "company-c360",
                    "c360_company_name": "C360 Cafe",
                    "usage_status": "live",
                    "nearest_distance_m": 260,
                    "selected_deal_status": "current_or_open_selected_deal",
                }
            ],
            google_places=[],
        )

        customers = result["answer"]["customers_nearby"]
        self.assertEqual(len(customers), 1)
        self.assertEqual(customers[0]["rank_category"], "c360_current_customer_without_stored_outlet")
        self.assertEqual(customers[0]["organisation_id"], "org-c360")

    def test_c360_current_customer_with_both_ids_gets_org_drilldown_url(self):
        result = self.module.merge_near_me_sources(
            "kaiyi@staffany.com",
            self.known_area("sg_raffles_place"),
            outlet_matches=[],
            c360_customer_rows=[
                {
                    "organisation_id": "org/c360",
                    "hubspot_company_id": "company c360",
                    "c360_company_name": "C360 Cafe",
                    "nearest_distance_m": 260,
                    "selected_deal_status": "current_or_open_selected_deal",
                }
            ],
            google_places=[],
        )

        customer = result["answer"]["customers_nearby"][0]
        self.assertEqual(
            customer["c360_url"],
            "https://customer-360-qv4r5xkisq-as.a.run.app/companies/company%20c360/orgs/org%2Fc360",
        )

    def test_known_numeric_company_id_uses_customer360_route_key(self):
        result = self.module.merge_near_me_sources(
            "kaiyi@staffany.com",
            self.known_area("sg_raffles_place"),
            outlet_matches=[],
            c360_customer_rows=[
                {
                    "organisation_id": "1991281569-org-001",
                    "hubspot_company_id": "1991281569",
                    "c360_company_name": "Fei Siong Group",
                    "nearest_distance_m": 260,
                    "selected_deal_status": "current_or_open_selected_deal",
                }
            ],
            google_places=[],
        )

        customer = result["answer"]["customers_nearby"][0]
        self.assertEqual(customer["customer360_route_key"], "fei-siong-group")
        self.assertEqual(
            customer["c360_url"],
            "https://customer-360-qv4r5xkisq-as.a.run.app/companies/fei-siong-group/orgs/1991281569-org-001",
        )

    def test_current_customer_with_company_id_only_gets_company_url(self):
        result = self.module.merge_near_me_sources(
            "kaiyi@staffany.com",
            self.known_area("sg_raffles_place"),
            outlet_matches=[],
            c360_customer_rows=[
                {
                    "hubspot_company_id": "company-only",
                    "c360_company_name": "Company Only Cafe",
                    "nearest_distance_m": 260,
                    "selected_deal_status": "current_or_open_selected_deal",
                }
            ],
            google_places=[],
        )

        customer = result["answer"]["customers_nearby"][0]
        self.assertEqual(
            customer["c360_url"],
            "https://customer-360-qv4r5xkisq-as.a.run.app/companies/company-only",
        )

    def test_unknown_numeric_company_id_does_not_render_dummy_c360_url(self):
        result = self.module.merge_near_me_sources(
            "kaiyi@staffany.com",
            self.known_area("sg_raffles_place"),
            outlet_matches=[],
            c360_customer_rows=[
                {
                    "hubspot_company_id": "123456789",
                    "c360_company_name": "Unknown Numeric Route Cafe",
                    "nearest_distance_m": 260,
                    "selected_deal_status": "current_or_open_selected_deal",
                }
            ],
            google_places=[],
        )

        customer = result["answer"]["customers_nearby"][0]
        self.assertNotIn("c360_url", customer)
        self.assertEqual(customer["confidence"], "needs-check")
        self.assertIn("Customer 360 route key was unavailable", result["caveat"])

    def test_confirmed_customer_outlet_gets_c360_company_url(self):
        result = self.module.merge_near_me_sources(
            "kaiyi@staffany.com",
            self.known_area("sg_raffles_place"),
            outlet_matches=[
                {
                    "outlet_location_id": "outlet-current",
                    "outlet_name": "Current Client Cafe",
                    "hubspot_company_id": "company-current",
                    "match_status": "confirmed",
                    "account_status": "customer",
                    "distance_m": 10,
                    "company": {"company_name": "Current Client Cafe", "hubspot_company_id": "company-current"},
                }
            ],
            c360_customer_rows=[],
            google_places=[],
        )

        customer = result["answer"]["customers_nearby"][0]
        self.assertEqual(customer["rank_category"], "confirmed_outlet_current_customer")
        self.assertEqual(
            customer["c360_url"],
            "https://customer-360-qv4r5xkisq-as.a.run.app/companies/company-current",
        )

    def test_current_customer_missing_company_id_keeps_row_with_caveat(self):
        result = self.module.merge_near_me_sources(
            "kaiyi@staffany.com",
            self.known_area("sg_raffles_place"),
            outlet_matches=[],
            c360_customer_rows=[
                {
                    "organisation_id": "org-missing-company",
                    "c360_company_name": "Missing Company Cafe",
                    "nearest_distance_m": 260,
                    "selected_deal_status": "current_or_open_selected_deal",
                }
            ],
            google_places=[],
        )

        customer = result["answer"]["customers_nearby"][0]
        self.assertNotIn("c360_url", customer)
        self.assertEqual(customer["confidence"], "needs-check")
        self.assertEqual(result["confidence"], "needs-check")
        self.assertIn("C360 link missing because Customer 360 route key was unavailable", result["caveat"])

    def test_prospect_outlet_does_not_outrank_current_customer(self):
        result = self.module.merge_near_me_sources(
            "kaiyi@staffany.com",
            self.known_area("sg_raffles_place"),
            outlet_matches=[
                {
                    "outlet_location_id": "prospect-outlet",
                    "outlet_name": "Prospect Grill",
                    "hubspot_company_id": "company-prospect",
                    "match_status": "confirmed",
                    "account_status": "prospect",
                    "distance_m": 10,
                    "company": {"company_name": "Prospect Grill", "hubspot_company_id": "company-prospect"},
                }
            ],
            c360_customer_rows=[
                {
                    "organisation_id": "org-customer",
                    "hubspot_company_id": "company-customer",
                    "c360_company_name": "Customer Grill",
                    "nearest_distance_m": 800,
                    "selected_deal_status": "current_or_open_selected_deal",
                }
            ],
            google_places=[],
        )

        ranked = result["answer"]["all_results"]
        self.assertEqual(ranked[0]["hubspot_company_id"], "company-customer")
        self.assertEqual(ranked[0]["rank_category"], "c360_current_customer_without_stored_outlet")
        self.assertEqual(ranked[1]["rank_category"], "confirmed_outlet_prospect")

    def test_google_only_restaurants_are_candidates_not_confirmed_accounts(self):
        result = self.module.merge_near_me_sources(
            "kaiyi@staffany.com",
            self.known_area("sg_raffles_place"),
            outlet_matches=[],
            c360_customer_rows=[],
            google_places=[
                {
                    "outlet_name": "Maps Only Noodles",
                    "google_place_id": "maps-only",
                    "formatted_address": "1 Example Road",
                    "distance_m": 50,
                }
            ],
        )

        self.assertEqual(len(result["answer"]["live_candidates"]), 1)
        candidate = result["answer"]["live_candidates"][0]
        self.assertEqual(candidate["rank_category"], "google_places_live_candidate")
        self.assertEqual(candidate["match_status"], "candidate")
        self.assertEqual(candidate["store_policy"], "live_candidate_only_until_review_approval")
        self.assertNotIn("c360_url", candidate)
        self.assertIn("Google-only restaurants are candidates", result["caveat"])

    def test_past_selected_deal_stays_visible_with_caveat(self):
        result = self.module.merge_near_me_sources(
            "kaiyi@staffany.com",
            self.known_area("sg_raffles_place"),
            outlet_matches=[],
            c360_customer_rows=[
                {
                    "organisation_id": "org-past",
                    "hubspot_company_id": "company-past",
                    "c360_company_name": "Past Deal Cafe",
                    "nearest_distance_m": 100,
                    "selected_deal_status": "past_selected_deal",
                    "deal_end_date": "2024-01-01",
                }
            ],
            google_places=[],
        )

        customers = result["answer"]["customers_nearby"]
        self.assertEqual(len(customers), 1)
        self.assertIn("Past selected deal", " ".join(customers[0]["rank_notes"]))
        self.assertIn("Past selected deal rows remain visible", result["caveat"])


if __name__ == "__main__":
    unittest.main()
