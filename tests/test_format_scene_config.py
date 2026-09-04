from pathlib import Path
import tempfile
import unittest

from format_scene_config import (
    SceneConfigFormatError,
    compact_short_scalar_arrays,
    format_file,
)


class SceneConfigFormatterTests(unittest.TestCase):
    def test_compacts_short_scalar_arrays_and_preserves_lexemes(self):
        source = '''{
  "position": [
    -1.00,
    2e-3,
    3
  ],
  "labels": [
    "a,b",
    "c"
  ]
}
'''
        expected = '''{
  "position": [-1.00, 2e-3, 3],
  "labels": ["a,b", "c"]
}
'''
        self.assertEqual(compact_short_scalar_arrays(source), expected)

    def test_keeps_outer_nested_and_object_arrays_expanded(self):
        source = '''{
  "points": [
    [
      1,
      2,
      3
    ],
    [
      4,
      5,
      6
    ]
  ],
  "objects": [
    {
      "name": "one"
    }
  ]
}
'''
        expected = '''{
  "points": [
    [1, 2, 3],
    [4, 5, 6]
  ],
  "objects": [
    {
      "name": "one"
    }
  ]
}
'''
        self.assertEqual(compact_short_scalar_arrays(source), expected)

    def test_keeps_arrays_over_item_limit_expanded(self):
        source = '''{
  "values": [
    1,
    2,
    3,
    4,
    5
  ]
}
'''
        self.assertEqual(compact_short_scalar_arrays(source), source)

    def test_rejects_invalid_json(self):
        with self.assertRaises(SceneConfigFormatError):
            compact_short_scalar_arrays('{"position": [1, 2}')

    def test_file_formatting_is_idempotent_and_checkable(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text('{\n  "up": [\n    0,\n    1,\n    0\n  ]\n}\n')
            self.assertTrue(format_file(path))
            self.assertEqual(path.read_text(), '{\n  "up": [0, 1, 0]\n}\n')
            self.assertFalse(format_file(path, check=True))
            self.assertFalse(format_file(path))


if __name__ == "__main__":
    unittest.main()
