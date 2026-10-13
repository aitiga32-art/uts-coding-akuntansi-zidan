import os
import unittest
from fastapi.testclient import TestClient
from backend.api import app


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.previous=os.environ.get('API_TOKEN')
        os.environ['API_TOKEN']='test-only-not-a-production-token'
        self.client=TestClient(app)
        self.headers={'Authorization':'Bearer test-only-not-a-production-token'}

    def tearDown(self):
        if self.previous is None: os.environ.pop('API_TOKEN',None)
        else: os.environ['API_TOKEN']=self.previous

    def test_auth_required(self):
        self.assertEqual(self.client.get('/journals').status_code,401)

    def test_posted_http_edit_delete_disabled(self):
        for method in (self.client.put,self.client.delete):
            self.assertEqual(method('/journals/1',headers=self.headers).status_code,405)

    def test_bad_payload(self):
        self.assertEqual(self.client.post('/vouchers',headers=self.headers,json={'lines':[]}).status_code,422)
