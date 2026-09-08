from copy import deepcopy
import json
from pathlib import Path
import unittest

from sunflowers import expand_organs, validate_sunflower, write_sunflower_field
from terrain import RollingHillside


def recipe():
    config = json.loads((Path(__file__).parent / "fixtures/canonical_config.json").read_text())
    pattern = config["scene_description"]["objects"][0]["construction"]
    pattern["support"]["stem"]["enabled"] = True
    return {"enabled": True, "construction": {"variants": 2, "pattern": pattern},
            "population": {"method": "scatter", "count": 12, "seed": 99,
                           "scale": [.8, 1.2], "region": {"center": [0, 0], "size": [50, 50]}}}


class SunflowerTests(unittest.TestCase):
    def setUp(self):
        self.terrain = RollingHillside({"size": [100, 100], "base_height": 7,
                                       "slope": {"grade": .1}, "noise": {"amplitude": 0}})

    @staticmethod
    def simple_head(lines, patterns):
        lines.extend(['ObjectBegin "seed"', 'Material "diffuse"',
                      'Shape "sphere" "float radius" [ 1 ]', 'ObjectEnd',
                      'AttributeBegin', 'Translate 0 72 0', 'ObjectInstance "seed"',
                      'AttributeEnd'])

    def test_expansion_preserves_organ_scope_and_removes_nested_instancing(self):
        original = []
        self.simple_head(original, [])
        result = expand_organs(original)
        self.assertEqual(result, ['AttributeBegin', 'Translate 0 72 0',
                                 'AttributeBegin', 'Material "diffuse"',
                                 'Shape "sphere" "float radius" [ 1 ]',
                                 'AttributeEnd', 'AttributeEnd'])
        with self.assertRaises(ValueError):
            expand_organs(['ObjectInstance "missing"'])

    def test_scatter_is_deterministic_and_geometry_is_defined_per_variant(self):
        entry = recipe()
        before = deepcopy(entry)
        a, b = [], []
        for lines in (a, b):
            write_sunflower_field(lines, self.terrain, entry, "field", self.simple_head)
        self.assertEqual(a, b)
        self.assertEqual(entry, before)
        self.assertEqual(sum(s.startswith('ObjectBegin') for s in a), 2)
        self.assertEqual(sum(s.startswith('ObjectInstance') for s in a), 12)
        self.assertEqual(sum(s.startswith('Shape ') for s in a), 2)
        inside = False
        for line in a:
            if line.startswith('ObjectBegin'): inside = True
            if line == 'ObjectEnd': inside = False
            if line.startswith('ObjectInstance'): self.assertFalse(inside)

    def test_explicit_placement_adds_terrain_height_and_keeps_root_anchor(self):
        entry = recipe()
        entry['population'] = {"method": "explicit", "y_offset": .25,
                               "instances": [{"position": [10, 2, 3], "variant": 1,
                                              "rotation_degrees": 30, "scale": 2}]}
        lines = []
        write_sunflower_field(lines, self.terrain, entry, "field", self.simple_head)
        y = self.terrain.sample(10, 3).height + 2.25
        self.assertIn(f'Translate 10 {y} 3', lines)
        self.assertIn('Scale 2 2 2', lines)
        self.assertIn('ObjectInstance "field_1"', lines)

    def test_invalid_population_and_missing_stalk_are_rejected(self):
        entry = recipe()
        self.assertEqual(validate_sunflower(entry['construction'], entry['population']), [])
        entry['construction']['pattern']['support']['stem']['enabled'] = False
        entry['population']['scale'] = [1, -1]
        entry['population']['count'] = -1
        self.assertEqual(len(validate_sunflower(entry['construction'], entry['population'])), 3)

    def test_impossible_scatter_fails_instead_of_silently_dropping_plants(self):
        entry = recipe()
        entry['population']['region']['center'] = [10000, 10000]
        with self.assertRaisesRegex(ValueError, 'accepted 0 of 12'):
            write_sunflower_field([], self.terrain, entry, "field", self.simple_head)
