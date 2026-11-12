import tempfile
import unittest
from pathlib import Path

from splashmodify.cli import ConsoleApp
from splashmodify.cli.console_ui import ConsoleUserInterface
from splashmodify.cli.menu import Command, Invalid, interpret_input
from splashmodify.cli.style import ASCII_SYMBOLS, UNICODE_SYMBOLS, Style
from splashmodify.cli.terminal import Console, _pick_symbols
from splashmodify.core import ActionError, LoadFailure, OperationCancelled, Parameter, ParameterKind
from tests.fakes import FakeModule, FakeTarget, RecordingAction, scripted_console

TITLES = ["PhpStorm", "PyCharm", "Rider"]


class InterpretInputTests(unittest.TestCase):
    def test_numbers_are_one_based(self):
        self.assertEqual(interpret_input("1", TITLES, allow_back=True), 0)
        self.assertEqual(interpret_input(" 3 ", TITLES, allow_back=True), 2)

    def test_out_of_range_and_unicode_digits_are_invalid(self):
        for text in ("4", "²"):
            result = interpret_input(text, TITLES, allow_back=True)
            self.assertIsInstance(result, Invalid)
        self.assertIn("1 to 3", interpret_input("9", TITLES, allow_back=True).message)

    def test_back_only_when_allowed(self):
        self.assertIs(interpret_input("0", TITLES, allow_back=True), Command.BACK)
        self.assertIs(interpret_input("b", TITLES, allow_back=True), Command.BACK)
        self.assertIsInstance(interpret_input("0", TITLES, allow_back=False), Invalid)

    def test_quit_words(self):
        for text in ("q", "Q", "quit", "exit"):
            self.assertIs(interpret_input(text, TITLES, allow_back=False), Command.QUIT)

    def test_name_matching(self):
        self.assertEqual(interpret_input("rider", TITLES, allow_back=True), 2)
        self.assertEqual(interpret_input("pych", TITLES, allow_back=True), 1)
        self.assertEqual(interpret_input("storm", TITLES, allow_back=True), 0)  # substring, unique
        ambiguous = interpret_input("p", TITLES, allow_back=True)
        self.assertIsInstance(ambiguous, Invalid)
        self.assertIn("PhpStorm", ambiguous.message)
        self.assertIsInstance(interpret_input("zzz", TITLES, allow_back=True), Invalid)

    def test_blank_input_is_silently_invalid(self):
        self.assertEqual(interpret_input("   ", TITLES, allow_back=True), Invalid(""))


class ConsoleUserInterfaceTests(unittest.TestCase):
    def test_ask_file_retries_until_existing_and_strips_quotes(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "my image.png"
            image.touch()
            console, output = scripted_console(["missing.png", f'"{image}"'])
            self.assertEqual(ConsoleUserInterface(console).ask_file("Image"), image)
            self.assertIn("File not found", output.getvalue())

    def test_empty_answer_cancels(self):
        console, _ = scripted_console(["", "  "])
        ui = ConsoleUserInterface(console)
        self.assertIsNone(ui.ask_file("Image"))
        self.assertIsNone(ui.ask_directory("Folder"))

    def test_ask_directory_rejects_files(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "file.txt"
            file.touch()
            console, output = scripted_console([str(file), directory])
            self.assertEqual(ConsoleUserInterface(console).ask_directory("Folder"), Path(directory))
            self.assertIn("Folder not found", output.getvalue())

    def test_ask_text_returns_none_for_blank(self):
        console, _ = scripted_console(["  ", " hi "])
        ui = ConsoleUserInterface(console)
        self.assertIsNone(ui.ask_text("Name"))
        self.assertEqual(ui.ask_text("Name"), "hi")


class SymbolTests(unittest.TestCase):
    def test_falls_back_to_ascii_when_encoding_cannot_show_symbols(self):
        class Stream:
            encoding = "ascii"

        class Utf8Stream:
            encoding = "utf-8"

        self.assertEqual(_pick_symbols(Stream()), ASCII_SYMBOLS)
        self.assertEqual(_pick_symbols(Utf8Stream()), UNICODE_SYMBOLS)

    def test_plain_style_adds_no_escape_codes(self):
        self.assertEqual(Style().bold("x"), "x")
        self.assertIn("\033[", Style(color=True).bold("x"))


def build_app(modules, answers, failures=()):
    console, output = scripted_console(answers)
    app = ConsoleApp(modules=modules, failures=failures, console=console, workspace=Path("."))
    return app, output


class ConsoleAppTests(unittest.TestCase):
    def test_full_navigation_across_modules_targets_and_actions(self):
        first, second = RecordingAction("First action"), RecordingAction("Second action")
        modules = [
            FakeModule("a", "Alpha", [FakeTarget("One", [first]), FakeTarget("Two", [second])]),
            FakeModule("b", "Beta", [FakeTarget("Three", [RecordingAction("Third")]), FakeTarget("Four", [])]),
        ]
        # module 1 > target 2 > action 1 (runs) > back > back > quit
        app, output = build_app(modules, ["1", "2", "1", "0", "0", "q"])
        self.assertEqual(app.run(), 0)

        self.assertEqual((len(first.calls), len(second.calls)), (0, 1))
        text = output.getvalue()
        self.assertIn("Choose a module", text)
        self.assertIn("Alpha > Two", text)
        self.assertIn("Second action done", text)

    def test_levels_with_a_single_choice_are_skipped(self):
        action = RecordingAction()
        app, output = build_app([FakeModule("a", "Alpha", [FakeTarget("Only", [action])])], ["1", "0"])
        self.assertEqual(app.run(), 0)  # "0" backs out of everything because no other level exists
        self.assertEqual(len(action.calls), 1)
        self.assertNotIn("Choose a module", output.getvalue())
        self.assertNotIn("Choose an application", output.getvalue())

    def test_breadcrumb_does_not_repeat_a_same_named_target(self):
        app, output = build_app([FakeModule("a", "Studio", [FakeTarget("studio", [RecordingAction()])])], ["q"])
        app.run()
        self.assertNotIn("Studio > studio", output.getvalue())

    def test_parameters_are_collected_before_running(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "a.png"
            image.touch()
            action = RecordingAction(parameters=[Parameter("image", "Image", ParameterKind.FILE)])
            app, _ = build_app([FakeModule("a", "Alpha", [FakeTarget("T", [action])])], ["1", str(image), "q"])
            app.run()
            self.assertEqual(action.calls, [{"image": image}])

    def test_cancelling_a_parameter_skips_the_action(self):
        action = RecordingAction(parameters=[Parameter("image", "Image", ParameterKind.FILE)])
        app, output = build_app([FakeModule("a", "Alpha", [FakeTarget("T", [action])])], ["1", "", "q"])
        app.run()
        self.assertEqual(action.calls, [])
        self.assertIn("Cancelled.", output.getvalue())

    def test_expected_and_unexpected_failures_keep_the_session_alive(self):
        actions = [
            RecordingAction("Expected", error=ActionError("Disk is full")),
            RecordingAction("Cancelled", error=OperationCancelled()),
            RecordingAction("Unexpected", error=RuntimeError("boom")),
            RecordingAction("Fine"),
        ]
        app, output = build_app([FakeModule("a", "Alpha", [FakeTarget("T", actions)])], ["1", "2", "3", "4", "q"])
        self.assertEqual(app.run(), 0)
        text = output.getvalue()
        self.assertIn("Disk is full", text)
        self.assertIn("Cancelled.", text)
        self.assertIn("Unexpected error: RuntimeError: boom", text)
        self.assertIn("Fine done", text)

    def test_load_failures_are_shown_in_the_banner(self):
        app, output = build_app([FakeModule("a", "Alpha", [FakeTarget("T", [RecordingAction()])])], ["q"],
                                failures=[LoadFailure("broken", "ImportError: nope")])
        app.run()
        self.assertIn("Module 'broken' was not loaded: ImportError: nope", output.getvalue())

    def test_no_modules_is_an_error_exit(self):
        app, output = build_app([], [])
        self.assertEqual(app.run(), 1)
        self.assertIn("No modules found", output.getvalue())

    def test_quitting_inside_a_prompt_leaves_the_application_without_an_error(self):
        action = RecordingAction(parameters=[Parameter("image", "Image", ParameterKind.FILE)])
        app, output = build_app([FakeModule("a", "Alpha", [FakeTarget("T", [action])])], ["1", "q"])
        self.assertEqual(app.run(), 0)
        self.assertEqual(action.calls, [])
        self.assertNotIn("Unexpected error", output.getvalue())

    def test_end_of_input_quits_cleanly(self):
        app, _ = build_app([FakeModule("a", "A", [FakeTarget("T1", [RecordingAction()]), FakeTarget("T2", [])]),
                            FakeModule("b", "B", [FakeTarget("T", [])])], [])
        self.assertEqual(app.run(), 0)

    def test_invalid_input_shows_a_hint_and_asks_again(self):
        app, output = build_app([FakeModule("a", "A", [FakeTarget("T1", [RecordingAction()]), FakeTarget("T2", [])]),
                                 FakeModule("b", "B", [FakeTarget("T", [])])], ["9", "nothing", "q"])
        app.run()
        self.assertIn("Enter a number from 1 to 2", output.getvalue())
        self.assertIn("Nothing matches", output.getvalue())


if __name__ == "__main__":
    unittest.main()
