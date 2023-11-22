import unittest
import requests

LOCAL_SERVER_ENDPOINT = 'http://0.0.0.0:8000'


class TestImageList(unittest.TestCase):
    def test_get_image_list(self):
        response = requests.get(f'{LOCAL_SERVER_ENDPOINT}/images/list')
        self.assertEqual(response.status_code, 200)
        self.assertIn('atomic-openshift-cluster-autoscaler', response.text)
