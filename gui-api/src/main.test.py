import unittest
import json

from main import app

from fixtures.agent import agent_fixture


class TransactionsTest(unittest.TestCase):
    def test_make_transfer(self):
        tester = app.test_client(self)
        response = tester.post(
            "/transfer",
            data=json.dumps(dict(recipient="123", value=100, mode="transfer")),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

        responseData = json.loads(response.data)
        self.assertEqual(responseData["status"], "success")


class AgentTest(unittest.TestCase):
    def test_get_agent(self):
        tester = app.test_client(self)
        response = tester.get("/agent")
        self.assertEqual(response.status_code, 200)

        responseData = json.loads(response.data)
        self.assertEqual(responseData["public_key"], agent_fixture["public_key"])
        self.assertEqual(responseData["secret_key"], agent_fixture["secret_key"])
        self.assertEqual(responseData["balance"], agent_fixture["balance"])
        self.assertEqual(responseData["stake"], agent_fixture["stake"])

    def test_generate_key_pairs(self):
        tester = app.test_client(self)
        response = tester.post("/keys")
        self.assertEqual(response.status_code, 200)

        responseData = json.loads(response.data)
        self.assertEqual(responseData["status"], "success")

    def test_get_dag_from_agent(self):
        tester = app.test_client(self)
        response = tester.get("/dag")
        self.assertEqual(response.status_code, 200)

        responseData = json.loads(response.data)
        self.assertEqual(len(responseData["nodes"]), 17)
        self.assertEqual(len(responseData["links"]), 41)


if __name__ == "__main__":
    unittest.main()
