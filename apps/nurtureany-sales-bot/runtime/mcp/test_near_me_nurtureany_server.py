import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

MCP_DIR = Path(__file__).resolve().parent
if str(MCP_DIR) not in sys.path:
    sys.path.insert(0, str(MCP_DIR))

from test_helpers import load_mcp_module


def load_near_me_module():
    return load_mcp_module("near_me_nurtureany_server.py", "near_me_nurtureany_server_under_test")


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

    def merge_near_me_sources(self, *args, **kwargs):
        kwargs.setdefault("include_debug_rows", True)
        return self.module.merge_near_me_sources(*args, **kwargs)

    def test_default_known_areas_cover_all_18_seed_areas(self):
        expected = [
            "sg_raffles_place",
            "sg_chinatown",
            "sg_bugis_junction",
            "sg_suntec_city",
            "sg_tanjong_pagar",
            "sg_ion_orchard",
            "sg_boat_quay_clarke_quay",
            "sg_marina_bay",
            "sg_westgate_jem",
            "sg_tampines_mall",
            "sg_plaza_singapura",
            "sg_paya_lebar_quarter",
            "sg_vivocity",
            "sg_northpoint_yishun",
            "sg_jewel_changi",
            "sg_nex",
            "sg_jurong_point",
            "sg_causeway_point",
        ]
        ids = [area["area_id"] for area in self.module.DEFAULT_KNOWN_AREAS]

        self.assertEqual(len(ids), 18)
        self.assertEqual(ids, expected)

    def test_raffles_place_alias_snaps_to_known_area(self):
        result = self.module.resolve_known_area_for_near_me(
            "kaiyi@staffany.com",
            location_text="test with Raffles Place",
        )

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(result["answer"]["area_id"], "sg_raffles_place")
        self.assertEqual(result["answer"]["snap_status"], "matched_by_alias")

    def test_new_area_aliases_snap_to_known_areas(self):
        cases = {
            "near Chinatown for lunch": "sg_chinatown",
            "walking around Tanjong Pagar": "sg_tanjong_pagar",
            "at Boat Quay now": "sg_boat_quay_clarke_quay",
            "around MBFC": "sg_marina_bay",
            "at PLQ": "sg_paya_lebar_quarter",
            "near Northpoint": "sg_northpoint_yishun",
        }

        for location_text, area_id in cases.items():
            with self.subTest(location_text=location_text):
                result = self.module.resolve_known_area_for_near_me(
                    "kaiyi@staffany.com",
                    location_text=location_text,
                )
                self.assertEqual(result["answer"]["area_id"], area_id)
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
        self.assertIn("`staffany-warehouse.analytics.customer_knowledge_latest`", sql)
        self.assertIn("`staffany-warehouse.analytics.customer_wiki_backfill_accounts`", sql)
        self.assertIn(
            "COALESCE(customer_latest.customer_slug, customer_backfill.customer_slug, customer_route_by_name.customer_slug) AS customer360_route_key",
            sql,
        )
        self.assertIn("customer_route_by_name", sql)
        self.assertIn("SAFE_CAST(c360.deal_end_date AS DATE) >= CURRENT_DATE()", sql)
        self.assertIn("COALESCE(ds.isarchived, FALSE) = FALSE", sql)
        self.assertIn("address_scope_terms", sql)
        self.assertIn("'collyer'", sql)
        self.assertIn("UNNEST(p.address_scope_terms)", sql)
        self.assertNotIn("section_rollup", sql)
        self.assertNotIn("ARRAY_AGG", sql)
        self.assertNotIn("nearby_sections", sql)
        self.assertIn(f"LIMIT {self.module.MAX_C360_CUSTOMER_QUERY_RESULTS}", sql)
        self.assertIn("ABS(raw_latitude) > 90", sql)
        self.assertNotIn("ClockRecords", sql)
        self.assertNotIn("CicoGeoData", sql)
        self.assertNotIn("employee", sql.lower())

    def test_c360_query_can_include_nearby_sections_for_seed_review(self):
        result = self.module.build_near_me_c360_customer_query(
            "kaiyi@staffany.com",
            area_id="sg_raffles_place",
            include_nearby_sections=True,
        )
        sql = result["answer"]["sql"]

        self.assertTrue(result["scope"]["include_nearby_sections"])
        self.assertIn("section_rollup", sql)
        self.assertIn("ARRAY_AGG", sql)
        self.assertIn("nearby_sections", sql)

    def test_c360_query_dataset_can_be_overridden_for_runtime(self):
        with patch.dict(os.environ, {"NURTUREANY_C360_DATASET": "analytics_staging"}):
            result = self.module.build_near_me_c360_customer_query(
                "kaiyi@staffany.com",
                area_id="sg_raffles_place",
            )
        sql = result["answer"]["sql"]

        self.assertEqual(result["answer"]["c360_dataset"], "analytics_staging")
        self.assertIn("`staffany-warehouse.analytics_staging.dim_sections`", sql)
        self.assertIn("`staffany-warehouse.analytics_staging.dim_org_section`", sql)
        self.assertIn("`staffany-warehouse.analytics_staging.fct_deal_org_company`", sql)
        self.assertIn("`staffany-warehouse.analytics_staging.customer_knowledge_latest`", sql)
        self.assertIn("`staffany-warehouse.analytics_staging.customer_wiki_backfill_accounts`", sql)

    def test_unresolved_runtime_env_placeholders_use_near_me_defaults(self):
        with patch.dict(
            os.environ,
            {
                "NURTUREANY_C360_DATASET": "${NURTUREANY_C360_DATASET}",
                "NURTUREANY_OUTLET_MATCHES_TABLE": "${NURTUREANY_OUTLET_MATCHES_TABLE}",
                "NURTUREANY_KNOWN_AREAS_FILE": "${NURTUREANY_KNOWN_AREAS_FILE}",
            },
        ):
            c360_result = self.module.build_near_me_c360_customer_query(
                "kaiyi@staffany.com",
                area_id="sg_raffles_place",
            )
            outlet_result = self.module.build_near_me_outlet_matches_query(
                "kaiyi@staffany.com",
                area_id="sg_raffles_place",
            )

        self.assertEqual(c360_result["answer"]["c360_dataset"], "analytics")
        self.assertIn("`staffany-warehouse.analytics.fct_deal_org_company`", c360_result["answer"]["sql"])
        self.assertIn(
            "`staffany-warehouse.analytics.nurtureany_near_me_outlet_matches`",
            outlet_result["answer"]["sql"],
        )

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
        self.assertIn("`staffany-warehouse.analytics.customer_knowledge_latest`", sql)
        self.assertIn("`staffany-warehouse.analytics.customer_wiki_backfill_accounts`", sql)
        self.assertIn("customer_route_by_name", sql)
        self.assertIn("LOWER(COALESCE(match_status, 'candidate')) != 'rejected'", sql)
        self.assertIn("hubspot_company_id", sql)
        self.assertIn("organisation_id", sql)
        self.assertIn("customer360_route_key", sql)
        self.assertIn(f"LIMIT {self.module.MAX_OUTLET_MATCH_RESULTS}", sql)
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
                        "businessStatus": "OPERATIONAL",
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
        self.assertEqual(place["google_business_status"], "OPERATIONAL")

    def test_seed_review_candidates_cap_at_10_and_mark_write_eligibility(self):
        google_places = [
            {
                "outlet_name": f"Maps Only {index}",
                "google_place_id": f"place-{index}",
                "formatted_address": f"{index} Example Road",
                "distance_m": index,
            }
            for index in range(20)
        ]

        result = self.module.prepare_near_me_seed_review_candidates(
            "kaiyi@staffany.com",
            "sg_raffles_place",
            google_places=google_places,
            c360_customer_rows=[
                {
                    "organisation_id": "org-c360",
                    "hubspot_company_id": "company-c360",
                    "c360_company_name": "C360 Cafe",
                    "nearest_distance_m": 260,
                    "selected_deal_status": "current_or_open_selected_deal",
                }
            ],
            hubspot_prospect_rows=[
                {
                    "hubspot_company_id": "company-prospect",
                    "company_name": "Prospect Bistro",
                    "outlet_name": "Prospect Bistro Raffles",
                    "formatted_address": "1 Raffles Place",
                    "google_place_id": "place-prospect",
                    "account_status": "prospect",
                    "nearest_distance_m": 120,
                }
            ],
            candidate_limit=50,
        )

        candidates = result["answer"]["review_candidates"]
        self.assertEqual(result["answer"]["candidate_count"], self.module.MAX_SEED_REVIEW_CANDIDATES_PER_AREA)
        self.assertEqual(result["answer"]["candidate_limit"], self.module.MAX_SEED_REVIEW_CANDIDATES_PER_AREA)
        self.assertEqual(candidates[0]["account_status"], "customer")
        self.assertFalse(candidates[0]["eligible_for_bigquery_write"])
        self.assertEqual(candidates[0]["ground_outlet_name_status"], "needs_ground_outlet_name")
        self.assertEqual(candidates[0]["review_action_required"], "add_ground_outlet_name_before_approval")
        self.assertEqual(candidates[1]["account_status"], "prospect")
        self.assertTrue(candidates[1]["eligible_for_bigquery_write"])
        self.assertFalse(any(
            candidate["eligible_for_bigquery_write"]
            for candidate in candidates
            if candidate["source_flags"] == ["google_places_live"]
        ))

    def test_seed_review_filters_c360_rows_outside_area_address_scope(self):
        result = self.module.prepare_near_me_seed_review_candidates(
            "kaiyi@staffany.com",
            "sg_raffles_place",
            google_places=[],
            c360_customer_rows=[
                {
                    "organisation_id": "org-valid",
                    "hubspot_company_id": "company-valid",
                    "c360_company_name": "Valid Raffles Customer",
                    "nearest_section_name": "The Arcade - Raffles Place",
                    "nearest_address": "11 Collyer Quay, Singapore 049317",
                    "nearest_distance_m": 41,
                    "selected_deal_status": "current_or_open_selected_deal",
                },
                {
                    "organisation_id": "org-west-mall",
                    "hubspot_company_id": "company-west-mall",
                    "c360_company_name": "Rumi Rangkayo Trading Pte Ltd",
                    "nearest_section_name": "West Mall",
                    "nearest_address": "#04-01 Bukit Batok Central Link West Mall, Singapore 658713",
                    "nearest_distance_m": 159,
                    "selected_deal_status": "current_or_open_selected_deal",
                },
            ],
        )

        names = [candidate["account_name"] for candidate in result["answer"]["review_candidates"]]
        self.assertEqual(names, ["Valid Raffles Customer"])

    def test_seed_review_expands_c360_sections_before_google_match(self):
        result = self.module.prepare_near_me_seed_review_candidates(
            "kaiyi@staffany.com",
            "sg_raffles_place",
            google_places=[
                {
                    "outlet_name": "BYD Boat Quay 1826 @ Boat Quay",
                    "google_place_id": "place-byd-boat-quay",
                    "formatted_address": "Level 1 - 3, 33/34 Boat Quay, Singapore 049822",
                    "google_business_status": "OPERATIONAL",
                    "distance_m": 173,
                }
            ],
            c360_customer_rows=[
                {
                    "organisation_id": "org-byd",
                    "hubspot_company_id": "company-byd",
                    "c360_company_name": "BYD by 1826",
                    "nearest_section_name": "STAFFIE-FOH",
                    "nearest_address": "6 Battery Road",
                    "nearest_distance_m": 80,
                    "selected_deal_status": "current_or_open_selected_deal",
                    "nearby_sections": [
                        {
                            "section_id": "section-staffie",
                            "section_name": "STAFFIE-FOH",
                            "section_address": "6 Battery Road",
                            "distance_m": 80,
                        },
                        {
                            "section_id": "section-byd-foh",
                            "section_name": "1826 - FOH",
                            "section_address": "Level 1 & 3, 33/34 Boat Quay Singapore 049822",
                            "latitude": 1.2862221296,
                            "longitude": 103.8498178,
                            "distance_m": 173,
                        },
                    ],
                }
            ],
            hubspot_prospect_rows=[],
        )

        candidates = result["answer"]["review_candidates"]
        self.assertEqual(candidates[0]["outlet_name"], "BYD Boat Quay 1826 @ Boat Quay")
        self.assertEqual(candidates[0]["hubspot_company_id"], "company-byd")
        self.assertEqual(candidates[0]["google_place_id"], "place-byd-boat-quay")
        self.assertTrue(candidates[0]["eligible_for_bigquery_write"])
        self.assertNotIn("Battery Road", candidates[0]["outlet_name"])

    def test_seed_review_can_confirm_section_verified_customer_without_google_place(self):
        result = self.module.prepare_near_me_seed_review_candidates(
            "kaiyi@staffany.com",
            "sg_raffles_place",
            google_places=[
                {
                    "outlet_name": "L'Entrecote @ Customs House",
                    "google_place_id": "closed-lentrecote",
                    "formatted_address": "70 Collyer Quay, #01-01 Customs House, Singapore 049323",
                    "google_business_status": "CLOSED_PERMANENTLY",
                    "distance_m": 205,
                }
            ],
            c360_customer_rows=[
                {
                    "organisation_id": "org-chimis",
                    "hubspot_company_id": "company-insurgence",
                    "c360_company_name": "Insurgence HQ Pte Ltd",
                    "nearest_distance_m": 205,
                    "selected_deal_status": "current_or_open_selected_deal",
                    "nearby_sections": [
                        {
                            "section_id": "section-chimis",
                            "section_name": "BOH Chimi's Especial @ Customs House",
                            "section_address": "",
                            "latitude": 1.2825241248,
                            "longitude": 103.8535038956,
                            "distance_m": 205,
                        }
                    ],
                }
            ],
            hubspot_prospect_rows=[],
        )

        candidates = result["answer"]["review_candidates"]
        chimis = next(candidate for candidate in candidates if candidate["account_name"] == "Insurgence HQ Pte Ltd")
        self.assertEqual(chimis["outlet_name"], "Chimi's Especial @ Customs House")
        self.assertEqual(chimis["google_place_id"], "")
        self.assertEqual(chimis["hubspot_company_id"], "company-insurgence")
        self.assertTrue(chimis["eligible_for_bigquery_write"])
        closed_google = next(candidate for candidate in candidates if candidate["google_place_id"] == "closed-lentrecote")
        self.assertFalse(closed_google["eligible_for_bigquery_write"])
        self.assertEqual(closed_google["review_action_required"], "verify_closed_or_relocated_place_before_approval")

    def test_seed_review_blocks_section_brand_account_conflict(self):
        result = self.module.prepare_near_me_seed_review_candidates(
            "kaiyi@staffany.com",
            "sg_bugis_junction",
            google_places=[],
            c360_customer_rows=[
                {
                    "organisation_id": "org-hot-hideout",
                    "hubspot_company_id": "company-hot-hideout",
                    "c360_company_name": "A Hot Hideout",
                    "nearest_section_name": "Ya Kun Kaya Toast (Bugis Junction)",
                    "nearest_address": "200 Victoria St, B1-11 Bugis Junction, Singapore 188021",
                    "nearest_distance_m": 100,
                    "selected_deal_status": "current_or_open_selected_deal",
                }
            ],
            hubspot_prospect_rows=[],
        )

        candidate = result["answer"]["review_candidates"][0]
        self.assertEqual(candidate["outlet_name"], "Ya Kun Kaya Toast (Bugis Junction) @ Victoria Street")
        self.assertFalse(candidate["eligible_for_bigquery_write"])
        self.assertEqual(candidate["review_action_required"], "verify_account_outlet_brand_before_approval")
        self.assertEqual(candidate["ground_outlet_name_status"], "needs_account_outlet_brand_review")
        self.assertIn("section_outlet_name_conflicts_with_account_name", candidate["data_quality_flags"])

    def test_seed_review_does_not_match_google_place_on_location_token_only(self):
        result = self.module.prepare_near_me_seed_review_candidates(
            "kaiyi@staffany.com",
            "sg_bugis_junction",
            google_places=[
                {
                    "outlet_name": "Ya Kun Kaya Toast (Bugis Junction)",
                    "google_place_id": "place-yakun-bugis",
                    "formatted_address": "200 Victoria St, B1-11 Bugis Junction, Singapore 188021",
                    "google_business_status": "OPERATIONAL",
                    "distance_m": 40,
                }
            ],
            c360_customer_rows=[
                {
                    "organisation_id": "org-hot-hideout",
                    "hubspot_company_id": "company-hot-hideout",
                    "c360_company_name": "A Hot Hideout",
                    "nearest_section_name": "A Hot Hideout @ Bugis",
                    "nearest_address": "200 Victoria St, Bugis Junction #03-30D, Singapore 188021",
                    "nearest_distance_m": 40,
                    "selected_deal_status": "current_or_open_selected_deal",
                }
            ],
            hubspot_prospect_rows=[],
        )

        candidates = result["answer"]["review_candidates"]
        hot_hideout = next(candidate for candidate in candidates if candidate["account_name"] == "A Hot Hideout")
        yakun = next(candidate for candidate in candidates if candidate["outlet_name"] == "Ya Kun Kaya Toast (Bugis Junction)")
        self.assertEqual(hot_hideout["google_place_id"], "")
        self.assertEqual(hot_hideout["outlet_name"], "A Hot Hideout @ Bugis")
        self.assertEqual(yakun["source_flags"], ["google_places_live"])
        self.assertFalse(yakun["eligible_for_bigquery_write"])

    def test_strong_name_address_match_rejects_same_unit_wrong_building(self):
        place = {
            "outlet_name": "Dimbulah Coffee @ RP",
            "formatted_address": "9 Raffles Place, #01-16/17, Republic Plaza, Singapore 048619",
        }
        wrong_outlet = {
            "outlet_name": "Dimbulah Coffee @ RP",
            "formatted_address": "30 Raffles Pl, #01-16/17, Singapore 048622",
        }

        self.assertFalse(self.module._strong_name_address_match(place, wrong_outlet))

    def test_strong_name_address_match_rejects_location_only_overlap(self):
        place = {
            "outlet_name": "Ya Kun Kaya Toast (Bugis Junction)",
            "formatted_address": "200 Victoria St, B1-11 Bugis Junction, Singapore 188021",
        }
        outlet = {
            "outlet_name": "A Hot Hideout @ Bugis",
            "formatted_address": "200 Victoria St, Bugis Junction #03-30D, Singapore 188021",
        }

        self.assertFalse(self.module._strong_name_address_match(place, outlet))

    def test_strong_name_address_match_rejects_closed_google_places(self):
        place = {
            "outlet_name": "Whiskdom Cookies and Brownies",
            "formatted_address": "1 Raffles Place, B1-06, Singapore 048616",
            "google_business_status": "CLOSED_PERMANENTLY",
        }
        outlet = {
            "outlet_name": "Whiskdom Cookies and Brownies",
            "formatted_address": "1 Raffles Place, B1-06, Singapore 048616",
        }

        self.assertFalse(self.module._strong_name_address_match(place, outlet))

    def test_strong_name_address_match_accepts_same_ground_name_and_building(self):
        place = {
            "outlet_name": "Origin Teahouse",
            "formatted_address": "11 Collyer Quay, #01-12, The Arcade, Singapore 049317",
            "google_business_status": "OPERATIONAL",
        }
        outlet = {
            "outlet_name": "Origin Teahouse",
            "formatted_address": "11 Collyer Quay #01-12, Singapore 049317",
        }

        self.assertTrue(self.module._strong_name_address_match(place, outlet))

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

        result = self.merge_near_me_sources(
            "kaiyi@staffany.com",
            self.known_area("sg_vivocity"),
            outlet_matches=outlets,
            c360_customer_rows=[],
            google_places=[],
        )

        customers = result["answer"]["customers_nearby"]
        self.assertEqual(len(customers), 1)
        self.assertEqual(customers[0]["company_name"], "Acme Group")
        self.assertEqual(len(customers[0]["outlet_locations"]), 2)

    def test_merge_blocks_when_c360_rows_are_omitted(self):
        result = self.merge_near_me_sources(
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
            google_places=[],
        )

        self.assertEqual(result["confidence"], "blocked")
        self.assertFalse(result["runtime_validation"]["can_answer"])
        self.assertEqual(result["runtime_validation"]["missing_required_source"], "C360 current-customer BigQuery rows")
        self.assertIn("build_near_me_c360_customer_query", result["next_required_steps"])

    def test_merge_returns_compact_bounded_payload(self):
        outlet_matches = [
            {
                "outlet_location_id": f"outlet-{index}",
                "outlet_name": f"Current Client Cafe {index}",
                "hubspot_company_id": f"company-{index}",
                "match_status": "confirmed",
                "account_status": "customer",
                "distance_m": index,
                "formatted_address": f"{index} Raffles Place, Singapore",
                "google_maps_uri": f"https://maps.google.com/?cid={index}",
                "company": {"company_name": f"Current Client Group {index}", "hubspot_company_id": f"company-{index}"},
                "large_unneeded_field": "x" * 2000,
            }
            for index in range(25)
        ]

        result = self.module.merge_near_me_sources(
            "kaiyi@staffany.com",
            self.known_area("sg_raffles_place"),
            outlet_matches=outlet_matches,
            c360_customer_rows=[],
            google_places=[],
        )

        answer = result["answer"]
        self.assertNotIn("all_results", answer)
        self.assertEqual(answer["counts"]["customers_nearby"], 25)
        self.assertEqual(answer["counts"]["returned_customers"], self.module.MAX_MERGED_CUSTOMERS_FOR_ANSWER)
        self.assertTrue(answer["truncated"]["customers_nearby"])
        self.assertIn("slack_answer", answer)
        self.assertIn("Customers to say hi to first:", answer["slack_answer"])
        self.assertNotIn("customers_nearby", answer)
        self.assertNotIn("prospects_nearby", answer)
        self.assertNotIn("live_candidates", answer)
        self.assertNotIn("Current Client Group 9", answer["slack_answer"])
        self.assertTrue(result["runtime_validation"]["can_answer"])
        self.assertLess(len(json.dumps(result)), 7000)

    def test_merge_verified_when_c360_query_executed_empty_and_no_candidates(self):
        result = self.merge_near_me_sources(
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

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(result["answer"]["counts"]["customers_nearby"], 1)
        self.assertTrue(result["runtime_validation"]["required_sources"]["c360_customer_rows"])

    def test_current_c360_customer_appears_without_outlet_location(self):
        result = self.merge_near_me_sources(
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
        self.assertEqual(customers[0]["company_name"], "C360 Cafe")

    def test_merge_filters_c360_rows_outside_area_address_scope(self):
        result = self.merge_near_me_sources(
            "kaiyi@staffany.com",
            self.known_area("sg_raffles_place"),
            outlet_matches=[],
            c360_customer_rows=[
                {
                    "organisation_id": "org-west-mall",
                    "hubspot_company_id": "company-west-mall",
                    "c360_company_name": "Rumi Rangkayo Trading Pte Ltd",
                    "nearest_section_name": "West Mall",
                    "nearest_address": "#04-01 Bukit Batok Central Link West Mall, Singapore 658713",
                    "nearest_distance_m": 159,
                    "selected_deal_status": "current_or_open_selected_deal",
                }
            ],
            google_places=[],
        )

        self.assertEqual(result["answer"]["customers_nearby"], [])
        self.assertEqual(result["answer"]["counts"]["all_results"], 0)

    def test_c360_current_customer_with_both_ids_gets_org_drilldown_url(self):
        result = self.merge_near_me_sources(
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
        result = self.merge_near_me_sources(
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
        self.assertEqual(
            customer["c360_url"],
            "https://customer-360-qv4r5xkisq-as.a.run.app/companies/fei-siong-group/orgs/1991281569-org-001",
        )

    def test_c360_row_route_key_renders_customer360_link(self):
        result = self.merge_near_me_sources(
            "kaiyi@staffany.com",
            self.known_area("sg_raffles_place"),
            outlet_matches=[],
            c360_customer_rows=[
                {
                    "organisation_id": "org-123",
                    "hubspot_company_id": "5217550822",
                    "customer360_route_key": "eu-yan-sang-international",
                    "c360_company_name": "Eu Yan Sang International Pte Ltd",
                    "nearest_distance_m": 22,
                    "selected_deal_status": "current_or_open_selected_deal",
                }
            ],
            google_places=[],
        )

        customer = result["answer"]["customers_nearby"][0]
        self.assertEqual(
            customer["c360_url"],
            "https://customer-360-qv4r5xkisq-as.a.run.app/companies/eu-yan-sang-international/orgs/org-123",
        )

    def test_unresolved_c360_template_env_uses_default_customer360_link(self):
        with patch.dict(
            os.environ,
            {
                "NURTUREANY_C360_COMPANY_URL_TEMPLATE": "{NURTUREANY_C360_COMPANY_URL_TEMPLATE}",
                "NURTUREANY_C360_ORG_URL_TEMPLATE": "{NURTUREANY_C360_ORG_URL_TEMPLATE}",
            },
        ):
            result = self.merge_near_me_sources(
                "kaiyi@staffany.com",
                self.known_area("sg_raffles_place"),
                outlet_matches=[],
                c360_customer_rows=[
                    {
                        "organisation_id": "org-123",
                        "hubspot_company_id": "5217550822",
                        "customer360_route_key": "eu-yan-sang-international",
                        "c360_company_name": "Eu Yan Sang International Pte Ltd",
                        "nearest_distance_m": 22,
                        "selected_deal_status": "current_or_open_selected_deal",
                    }
                ],
                google_places=[],
            )

        customer = result["answer"]["customers_nearby"][0]
        self.assertEqual(
            customer["c360_url"],
            "https://customer-360-qv4r5xkisq-as.a.run.app/companies/eu-yan-sang-international/orgs/org-123",
        )

    def test_invalid_c360_template_env_falls_back_to_default_customer360_link(self):
        with patch.dict(
            os.environ,
            {
                "NURTUREANY_C360_COMPANY_URL_TEMPLATE": "https://c360.test/{unknown_placeholder}",
                "NURTUREANY_C360_ORG_URL_TEMPLATE": "https://c360.test/{unknown_placeholder}/orgs/{organisation_id}",
            },
        ):
            result = self.merge_near_me_sources(
                "kaiyi@staffany.com",
                self.known_area("sg_raffles_place"),
                outlet_matches=[],
                c360_customer_rows=[
                    {
                        "organisation_id": "org-123",
                        "hubspot_company_id": "5217550822",
                        "customer360_route_key": "eu-yan-sang-international",
                        "c360_company_name": "Eu Yan Sang International Pte Ltd",
                        "nearest_distance_m": 22,
                        "selected_deal_status": "current_or_open_selected_deal",
                    }
                ],
                google_places=[],
            )

        customer = result["answer"]["customers_nearby"][0]
        self.assertEqual(
            customer["c360_url"],
            "https://customer-360-qv4r5xkisq-as.a.run.app/companies/eu-yan-sang-international/orgs/org-123",
        )

    def test_current_customer_with_company_id_only_gets_company_url(self):
        result = self.merge_near_me_sources(
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
        result = self.merge_near_me_sources(
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
        result = self.merge_near_me_sources(
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
        result = self.merge_near_me_sources(
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
        result = self.merge_near_me_sources(
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

        customers = result["answer"]["customers_nearby"]
        prospects = result["answer"]["prospects_nearby"]
        self.assertEqual(customers[0]["company_name"], "Customer Grill")
        self.assertEqual(customers[0]["rank_category"], "c360_current_customer_without_stored_outlet")
        self.assertEqual(prospects[0]["rank_category"], "confirmed_outlet_prospect")

    def test_google_only_restaurants_are_candidates_not_confirmed_accounts(self):
        result = self.merge_near_me_sources(
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
        result = self.merge_near_me_sources(
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
