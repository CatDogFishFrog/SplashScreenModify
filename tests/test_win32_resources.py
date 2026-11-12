import sys
import unittest
from pathlib import Path
from unittest import mock

from splashmodify.system.win32_resources import ResourceUpdate, update_resources


def fake_api(*, begin=1, update=1, end=1):
    api = mock.Mock()
    api.BeginUpdateResourceW.return_value = begin
    api.UpdateResourceW.return_value = update
    api.EndUpdateResourceW.return_value = end
    return api


UPDATES = (ResourceUpdate("BINARY", 120, 1033, b"abc"), ResourceUpdate("BINARY", 121, 1033, b"defg"))


class UpdateResourcesTests(unittest.TestCase):
    def test_updates_everything_and_commits(self):
        api = fake_api()
        update_resources(Path("Unity.dll"), UPDATES, kernel32=api)

        api.BeginUpdateResourceW.assert_called_once_with("Unity.dll", False)
        self.assertEqual(api.UpdateResourceW.call_count, 2)
        first = api.UpdateResourceW.call_args_list[0].args
        self.assertEqual((first[3], first[5]), (1033, 3))
        api.EndUpdateResourceW.assert_called_once_with(1, False)

    def test_does_nothing_without_updates(self):
        api = fake_api()
        update_resources(Path("Unity.dll"), (), kernel32=api)
        api.BeginUpdateResourceW.assert_not_called()

    def test_discards_all_changes_when_one_update_fails(self):
        api = fake_api(update=0)
        with self.assertRaises(OSError):
            update_resources(Path("Unity.dll"), UPDATES, kernel32=api)
        api.EndUpdateResourceW.assert_called_once_with(1, True)

    def test_reports_a_file_that_cannot_be_opened(self):
        api = fake_api(begin=0)
        with self.assertRaises(OSError):
            update_resources(Path("Unity.dll"), UPDATES, kernel32=api)
        api.UpdateResourceW.assert_not_called()
        api.EndUpdateResourceW.assert_not_called()

    def test_reports_a_failed_commit(self):
        with self.assertRaises(OSError):
            update_resources(Path("Unity.dll"), UPDATES, kernel32=fake_api(end=0))

    @unittest.skipIf(sys.platform == "win32", "перевірка поведінки поза Windows")
    def test_outside_windows_the_error_is_clear(self):
        with self.assertRaisesRegex(OSError, "Windows"):
            update_resources(Path("Unity.dll"), UPDATES)


if __name__ == "__main__":
    unittest.main()
