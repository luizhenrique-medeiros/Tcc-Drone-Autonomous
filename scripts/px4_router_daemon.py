"""Run MAVProxy headlessly on Windows without a terminal-backed prompt."""

import runpy
import sys

from MAVProxy.modules.lib import rline
from prompt_toolkit import PromptSession
from prompt_toolkit.input import DummyInput
from prompt_toolkit.output import DummyOutput


def headless_prompt() -> PromptSession:
    return PromptSession(input=DummyInput(), output=DummyOutput())


# MAVProxy constructs its prompt even when --non-interactive is selected.
rline.PromptSession = headless_prompt
sys.argv = [
    "mavproxy",
    "--master=COM7",
    "--baudrate=57600",
    "--out=udpout:127.0.0.1:14555",
    "--out=udpout:127.0.0.1:14600",
    "--source-system=253",
    "--no-console",
    "--no-state",
    "--streamrate=-1",
    "--non-interactive",
]
runpy.run_module("MAVProxy.mavproxy", run_name="__main__")
