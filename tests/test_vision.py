import unittest
from unittest.mock import Mock, patch

from PIL import Image

from material_intelligence.api.vision import Detection, find_visual_matches, parse_detections


class VisionTests(unittest.TestCase):
    def test_resized_boxes_to_crops_and_truncated_response(self):
        output = '''```json
        [{"label": "lamp", "bbox_2d": [-5, 20, 45, 45]},
         {"label": "outside", "bbox_2d": [500, 2, 550, 20]},
         {"label": "invalid", "bbox_2d": [10.1, 1, 10.1, 30]},
         {"label": "degenerate", "bbox_2d": [30, 25, 10, 5]},
         {"label": "truncated", "bbox_2d": [2, 3'''
        self.assertEqual(parse_detections(output, (200, 80), (100, 40)), [
            Detection(label="lamp", box=(0, 40, 90, 80)),
        ])

    def test_google_lens_uses_uploaded_crop_id(self):
        uploaded = Mock()
        uploaded.json.return_value = {"image_id": "crop-id"}
        result = Mock()
        result.json.return_value = {"visual_matches": [
            {"title": "Pendant lamp", "link": "https://example.com/pendant", "source": "Example"},
        ]}
        with patch("material_intelligence.api.vision.requests.post", return_value=uploaded) as post, patch(
            "material_intelligence.api.vision.requests.get", return_value=result
        ) as get:
            matches = find_visual_matches(Image.new("RGB", (30, 40)), "pendant", api_key="test")
        self.assertEqual(post.call_args.kwargs["files"]["image"][2], "image/jpeg")
        self.assertEqual(get.call_args.kwargs["params"]["image_id"], "crop-id")
        self.assertEqual(get.call_args.kwargs["params"]["q"], "pendant")
        self.assertEqual(matches[0].url, "https://example.com/pendant")
