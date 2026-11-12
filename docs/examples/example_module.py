"""Minimal custom module. Copy this file into splashmodify/modules/ and restart the tool.

It shows the three contracts a module implements (Module -> Target -> Action) and a
parameter the application asks for before running the action.
"""

from collections.abc import Sequence

from splashmodify.core import Action, ActionContext, Arguments, Module, Parameter, Target


class WriteGreetingAction(Action):
    title = "Write a greeting"
    description = "Create greeting.txt in the workspace folder"
    parameters = (Parameter(name="name", prompt="Who should be greeted"),)

    def run(self, context: ActionContext, arguments: Arguments) -> None:
        greeting_file = context.workspace / "greeting.txt"
        greeting_file.write_text(f"Hello, {arguments['name']}!\n", encoding="utf-8")
        context.ui.success(f"Written {greeting_file}")


class GreetingTarget(Target):
    title = "Greeting"
    description = "A file with a friendly message"

    def actions(self) -> Sequence[Action]:
        return (WriteGreetingAction(),)


class ExampleModule(Module):
    id = "example"
    title = "Example module"
    description = "Shows how to write a module"

    def targets(self) -> Sequence[Target]:
        return (GreetingTarget(),)


def create_module() -> Module:
    return ExampleModule()
