"""Synthetic catalog discovery; no game assets or live identifiers."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import mob_processor as m

class CatalogTests(unittest.TestCase):
    def test_recursive_overlap_and_case(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); sub = root/'eco'/'family'; sub.mkdir(parents=True)
            for name in ('Model.glb', 'model.glb'):
                (sub/name).write_bytes(b'synthetic')
            readme=root/'README.md'; readme.write_text('catalog notes')
            self.assertEqual(m.catalog_names([root, sub, root/'.', readme]), {'Model.glb', 'model.glb'})

    def test_duplicate_conflict_and_identical_aliases(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for folder in ('a', 'b'):
                (root/folder).mkdir()
                (root/folder/'Same.glb').write_bytes(b'one')
            self.assertEqual(m.catalog_names([root]), {'Same.glb'})
            (root/'b'/'Same.glb').write_bytes(b'two')
            with self.assertRaisesRegex(ValueError, 'Conflicting'):
                m.catalog_names([root])

    def test_symlinks_and_invalid_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); catalog = root/'catalog'; catalog.mkdir()
            asset = root/'asset.glb'; asset.write_bytes(b'synthetic')
            (catalog/'Alias.glb').symlink_to(asset)
            (catalog/'outside').symlink_to(root, target_is_directory=True)
            self.assertEqual(m.catalog_names([catalog]), {'Alias.glb'})
            with self.assertRaisesRegex(ValueError, 'symlink'):
                m.catalog_names([catalog/'outside'])
            with self.assertRaises(ValueError): m.catalog_names([asset])
            with self.assertRaises(FileNotFoundError): m.catalog_names([root/'missing'])
            (catalog/'Broken.glb').symlink_to(root/'missing')
            with self.assertRaises(ValueError): m.catalog_names([catalog])

    def test_large_catalog_and_discovery_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for i in range(201): (root/f'{i}.glb').touch()
            with patch('hashlib.file_digest', side_effect=AssertionError('Unique file hashed')):
                self.assertEqual(len(m.catalog_names([root])), 201)
            with self.assertRaisesRegex(ValueError, 'limit'):
                m.catalog_names([root], max_files=200)

if __name__ == '__main__': unittest.main()
