from pathlib import Path
import tempfile
import unittest

import ge360_agent.smart as smart


AGENTS = [
    {"id": "ge360_sysadmin", "description": "Debian systemd Linux"},
    {"id": "ge360_docker", "description": "Docker Compose containers"},
    {"id": "ge360_developer", "description": "Code Git tests"},
    {"id": "ge360_crm", "description": "SuiteCRM Mautic Prospex"},
    {"id": "ge360_automation", "description": "n8n workflow webhook"},
    {"id": "ge360_wordpress_seo", "description": "WordPress SEO"},
]


class SmartRouterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_runtime = smart.RUNTIME
        smart.RUNTIME = Path(self.tmp.name)

    def tearDown(self):
        smart.RUNTIME = self.old_runtime
        self.tmp.cleanup()

    def test_routes_suitecrm_to_crm_with_docker_collaboration(self):
        route = smart.route_task(
            "SuiteCRM worker unhealthy. Controlla Docker Compose e scheduler senza toccare il database.",
            AGENTS,
        )
        self.assertEqual(route.primary_agent, "ge360_crm")
        self.assertIn("ge360_docker", route.collaborators)
        self.assertIn(route.model, {"gpt-5.6-terra", "gpt-5.6-sol"})

    def test_simple_systemd_uses_luna(self):
        route = smart.route_task(
            "Controlla systemd e i log del servizio Debian.",
            AGENTS,
        )
        self.assertEqual(route.primary_agent, "ge360_sysadmin")
        self.assertEqual(route.model, "gpt-5.6-luna")

    def test_redacts_common_secrets(self):
        preview = smart.safe_preview(
            "password=supersegreta token:abcdef123456 api_key=xyz987"
        )
        self.assertNotIn("supersegreta", preview)
        self.assertNotIn("abcdef123456", preview)
        self.assertNotIn("xyz987", preview)
        self.assertIn("[REDACTED]", preview)

    def test_feedback_influences_similar_route(self):
        initial = smart.route_task(
            "Docker Compose worker unhealthy healthcheck container",
            AGENTS,
        )
        smart.remember_launch("ge360-smart-test", "Docker Compose worker unhealthy healthcheck container", initial)
        self.assertTrue(smart.feedback("ge360-smart-test", 1))
        learned = smart.route_task(
            "Docker Compose container worker unhealthy healthcheck",
            AGENTS,
        )
        self.assertEqual(learned.primary_agent, "ge360_docker")
        self.assertGreaterEqual(learned.matched["ge360_docker"], initial.matched["ge360_docker"])

    def test_delegation_prompt_has_real_newlines(self):
        route = smart.route_task("Controlla Docker Compose", AGENTS)
        prompt = smart.build_delegation_prompt("Controlla Docker Compose", route)
        self.assertIn("\n\nINCARICO UTENTE:\n", prompt)


if __name__ == "__main__":
    unittest.main()
