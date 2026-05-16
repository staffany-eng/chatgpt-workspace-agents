from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from test_helpers import load_mcp_module


class LaunchbotIfiServerTest(unittest.TestCase):
    def setUp(self):
        self.module = load_mcp_module("launchbot_ifi_server.py")

    def test_exposes_preview_and_confirmed_mutation_tools_only(self):
        self.assertEqual(
            sorted(tool.__name__ for tool in self.module.mcp.tools),
            [
                "create_or_update_ifi_feature_request_from_bd_note",
                "create_or_update_ifi_feature_request_tracking",
                "preview_ifi_feature_request_from_bd_note",
                "preview_ifi_feature_request_tracking",
            ],
        )
        tool_names = " ".join(tool.__name__ for tool in self.module.mcp.tools)
        self.assertNotIn("post_slack", tool_names)
        self.assertNotIn("chat_postMessage", tool_names)

    def test_preview_resolves_hubspot_url_and_builds_dedupe_jql(self):
        jira_searches = []

        def fake_hubspot_get(path):
            self.assertIn("/crm/v3/objects/companies/1991281569", path)
            return {
                "id": "1991281569",
                "properties": {
                    "name": "Acme Foods",
                    "domain": "acme.example",
                    "lifecyclestage": "customer",
                },
            }

        def fake_jira_post(path, body):
            self.assertEqual(path, "/rest/api/3/search/jql")
            jira_searches.append(body["jql"])
            return {
                "issues": [
                    {
                        "key": "IFI-100",
                        "fields": {
                            "summary": "Citibank bank file export",
                            "status": {"name": "Todo"},
                            "issuetype": {"name": "Submit a request or incident"},
                            "updated": "2026-05-15T09:00:00.000+0800",
                            "customfield_10881": "1991281569",
                            "issuelinks": [],
                        },
                    }
                ]
            }

        with patch.dict(
            os.environ,
            {
                "HUBSPOT_ACCESS_TOKEN": "hubspot-token",
                "JIRA_EMAIL": "bot@staffany.com",
                "JIRA_API_TOKEN": "jira-token",
            },
            clear=True,
        ), patch.object(self.module, "_hubspot_get", side_effect=fake_hubspot_get), patch.object(
            self.module, "_jira_post", side_effect=fake_jira_post
        ):
            result = self.module.preview_ifi_feature_request_tracking(
                hubspot_company="https://app.hubspot.com/contacts/4137076/company/1991281569",
                feature_gap="Citibank bank file export",
                original_question="Can we do Citibank bank file?",
                requester="@kerren",
                slack_permalink="https://staffany.slack.com/archives/C01/p1",
                linked_ker_key="KER-746",
            )

        self.assertEqual(result["confidence"], "verified")
        answer = result["answer"]
        self.assertEqual(answer["operation"], "update")
        self.assertEqual(answer["hubspotCompany"]["hubspotCompanyId"], "1991281569")
        self.assertIn('"HubSpot Company ID" ~ "1991281569"', jira_searches[0])
        self.assertIn('text ~ "citibank"', jira_searches[0])
        self.assertFalse(answer["willMutateJira"])
        self.assertFalse(answer["willPostMessage"])
        self.assertIn("HubSpot Company ID: 1991281569", answer["jiraIssuePayload"]["descriptionPreview"])

    def test_ambiguous_company_search_falls_back_to_candidates_without_auto_mapping(self):
        hubspot_queries = []

        def fake_hubspot_post(path, body):
            self.assertEqual(path, "/crm/v3/objects/companies/search")
            hubspot_queries.append(body["query"])
            if body["query"] == "neon group":
                return {"results": []}
            if body["query"] == "neon":
                return {
                    "results": [
                        {
                            "id": "25638156628",
                            "properties": {
                                "name": "Victory Hill Exhibitions Pte Ltd",
                                "domain": "neonglobal.com",
                                "lifecyclestage": "customer",
                            },
                        },
                        {
                            "id": "1884437991",
                            "properties": {
                                "name": "Neon Pigeon",
                                "domain": "neonpigeonsg.com",
                                "lifecyclestage": "marketingqualifiedlead",
                            },
                        },
                    ]
                }
            return {"results": []}

        with patch.object(self.module, "_hubspot_post", side_effect=fake_hubspot_post), patch.object(
            self.module, "_jira_post"
        ) as jira_post:
            result = self.module.preview_ifi_feature_request_tracking(
                hubspot_company="neon group",
                feature_gap="Citibank bank file export",
                original_question="Can we do Citibank bank file?",
            )

        self.assertEqual(result["confidence"], "needs-check")
        self.assertEqual(hubspot_queries, ["neon group", "neon"])
        self.assertEqual(result["answer"]["hubspotCandidates"][0]["hubspotCompanyId"], "25638156628")
        self.assertIn("HubSpot company link", result["answer"]["nextAction"])
        jira_post.assert_not_called()

    def test_bd_note_preview_requires_confirmed_company_when_alias_is_ambiguous(self):
        def fake_hubspot_post(path, body):
            if body["query"] == "Neon Group":
                return {"results": []}
            if body["query"] == "Neon":
                return {
                    "results": [
                        {
                            "id": "25638156628",
                            "properties": {
                                "name": "Victory Hill Exhibitions Pte Ltd",
                                "domain": "neonglobal.com",
                                "lifecyclestage": "customer",
                            },
                        }
                    ]
                }
            return {"results": []}

        with patch.object(self.module, "_hubspot_post", side_effect=fake_hubspot_post), patch.object(
            self.module, "_jira_post"
        ) as jira_post:
            result = self.module.preview_ifi_feature_request_from_bd_note(
                bd_note="Neon Group asked whether StaffAny can generate a native Citibank payroll bank file.",
                requester="@kerren",
            )

        self.assertEqual(result["confidence"], "needs-check")
        self.assertEqual(result["answer"]["bdNoteExtraction"]["companyHint"], "Neon Group")
        self.assertEqual(result["answer"]["bdNoteExtraction"]["featureGap"], "Citibank bank file export")
        self.assertEqual(result["answer"]["hubspotCandidates"][0]["hubspotCompanyId"], "25638156628")
        jira_post.assert_not_called()

    def test_bd_note_preview_with_confirmed_company_uses_shared_ifi_preview_contract(self):
        with patch.object(self.module, "_resolve_hubspot_company") as resolve_company, patch.object(
            self.module, "_search_existing_ifi"
        ) as search_existing:
            resolve_company.return_value = (
                "verified",
                {
                    "hubspotCompanyId": "25638156628",
                    "name": "Victory Hill Exhibitions Pte Ltd",
                    "domain": "neonglobal.com",
                    "lifecycleStage": "customer",
                    "hubspotUrl": "https://app.hubspot.com/contacts/4137076/company/25638156628",
                },
            )
            search_existing.return_value = (
                'project = IFI AND "HubSpot Company ID" ~ "25638156628" AND text ~ "citibank" ORDER BY updated DESC',
                [
                    {
                        "issueKey": "IFI-300",
                        "summary": "Citibank bank file export",
                        "status": "Todo",
                        "url": "https://staffany.atlassian.net/browse/IFI-300",
                    }
                ],
            )

            result = self.module.preview_ifi_feature_request_from_bd_note(
                bd_note="Neon Group asked whether StaffAny can generate a native Citibank payroll bank file.",
                hubspot_company="25638156628",
                requester="@kerren",
                slack_permalink="https://staffany.slack.com/archives/C01/p1",
                linked_ker_key="KER-746",
            )

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(result["answer"]["operation"], "update")
        self.assertEqual(result["answer"]["existingIssue"]["issueKey"], "IFI-300")
        self.assertEqual(result["answer"]["hubspotCompany"]["hubspotCompanyId"], "25638156628")
        self.assertEqual(result["answer"]["bdNoteExtraction"]["featureGap"], "Citibank bank file export")

    def test_bd_note_confirmed_write_blocks_without_exact_confirmation(self):
        with patch.object(self.module, "_resolve_hubspot_company") as resolve_company, patch.object(
            self.module, "_search_existing_ifi"
        ) as search_existing, patch.object(
            self.module, "_jira_post"
        ) as jira_post:
            resolve_company.return_value = (
                "verified",
                {
                    "hubspotCompanyId": "25638156628",
                    "name": "Victory Hill Exhibitions Pte Ltd",
                    "domain": "neonglobal.com",
                    "lifecycleStage": "customer",
                    "hubspotUrl": "https://app.hubspot.com/contacts/4137076/company/25638156628",
                },
            )
            search_existing.return_value = (
                'project = IFI AND "HubSpot Company ID" ~ "25638156628" AND text ~ "citibank" ORDER BY updated DESC',
                [],
            )

            result = self.module.create_or_update_ifi_feature_request_from_bd_note(
                bd_note="Neon Group asked whether StaffAny can generate a native Citibank payroll bank file.",
                hubspot_company="25638156628",
                requester="@kerren",
                approval_marker="yes",
            )

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("confirm IFI", result["answer"]["message"])
        self.assertEqual(result["answer"]["preview"]["operation"], "create")
        jira_post.assert_not_called()

    def test_create_blocks_without_exact_confirmation(self):
        with patch.object(self.module, "_resolve_hubspot_company") as resolve_company, patch.object(
            self.module, "_search_existing_ifi"
        ) as search_existing:
            resolve_company.return_value = (
                "verified",
                {
                    "hubspotCompanyId": "1991281569",
                    "name": "Acme Foods",
                    "domain": "",
                    "lifecycleStage": "customer",
                    "hubspotUrl": "https://app.hubspot.com/contacts/4137076/company/1991281569",
                },
            )
            search_existing.return_value = (
                'project = IFI AND "HubSpot Company ID" ~ "1991281569" ORDER BY updated DESC',
                [],
            )

            result = self.module.create_or_update_ifi_feature_request_tracking(
                hubspot_company="1991281569",
                feature_gap="Citibank bank file export",
                original_question="Can we do Citibank bank file?",
                approval_marker="yes",
            )

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("confirm IFI", result["answer"]["message"])
        self.assertEqual(result["answer"]["preview"]["operation"], "create")

    def test_create_new_ifi_after_confirmation_sets_hubspot_field_and_links_ker(self):
        jira_posts = []
        jira_puts = []

        with patch.object(self.module, "_resolve_hubspot_company") as resolve_company, patch.object(
            self.module, "_search_existing_ifi"
        ) as search_existing, patch.object(self.module, "_jira_post") as jira_post, patch.object(
            self.module, "_jira_get"
        ) as jira_get, patch.object(
            self.module, "_jira_put"
        ) as jira_put:
            resolve_company.return_value = (
                "verified",
                {
                    "hubspotCompanyId": "1991281569",
                    "name": "Acme Foods",
                    "domain": "",
                    "lifecycleStage": "customer",
                    "hubspotUrl": "https://app.hubspot.com/contacts/4137076/company/1991281569",
                },
            )
            search_existing.return_value = (
                'project = IFI AND "HubSpot Company ID" ~ "1991281569" ORDER BY updated DESC',
                [],
            )

            def fake_jira_post(path, body):
                jira_posts.append((path, body))
                if path == "/rest/api/3/issue":
                    return {"key": "IFI-200"}
                if path == "/rest/api/3/issueLink":
                    return {}
                raise AssertionError(path)

            jira_post.side_effect = fake_jira_post
            jira_get.return_value = {"fields": {"issuelinks": []}}
            jira_put.side_effect = lambda path, body: jira_puts.append((path, body)) or {}

            result = self.module.create_or_update_ifi_feature_request_tracking(
                hubspot_company="1991281569",
                feature_gap="Citibank bank file export",
                original_question="Can we do Citibank bank file?",
                requester="@kerren",
                slack_permalink="https://staffany.slack.com/archives/C01/p1",
                linked_ker_key="KER-746",
                approval_marker="confirm IFI",
            )

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(result["answer"]["operation"], "created")
        create_payload = jira_posts[0][1]["fields"]
        self.assertEqual(create_payload["project"]["key"], "IFI")
        self.assertEqual(create_payload["issuetype"]["id"], "10151")
        self.assertEqual(create_payload["customfield_10881"], "1991281569")
        self.assertEqual(jira_posts[1][0], "/rest/api/3/issueLink")
        self.assertEqual(jira_posts[1][1]["outwardIssue"]["key"], "KER-746")
        self.assertEqual(jira_puts, [])
        self.assertIn("Launchbot automation: IFI tracked", result["answer"]["slackReply"])


if __name__ == "__main__":
    unittest.main()
