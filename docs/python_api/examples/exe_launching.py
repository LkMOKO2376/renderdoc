# these imports are not strictly necessary, but are convenient
import dhr
import qdhr

# this is here to give autocomplete when editing the example
# in VS Code where it doesn't know about this global
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pydhr = qdhr.CaptureContext()

pydhr.ShowCaptureDialog()
dialog = pydhr.GetCaptureDialog()

exe = pydhr.Extensions().OpenFileName("Find an executable", "", "*.exe")

dialog.SetExecutableFilename(exe)

dialog.SetCommandLine("--cool-level very")

settings = dialog.Settings()

# we could also set the command line here, this is identical to SetCommandLine() above
print(settings.commandLine)

# reset anything the user has changed to default
settings.options = dhr.CaptureOptions()

# enable callstack capture
settings.options.captureCallstacks = True

dialog.SetSettings(settings)

opts = [qdhr.DialogButton.Yes, qdhr.DialogButton.No]
go = pydhr.Extensions().QuestionDialog("Ready to Launch?", opts, "Final Check")

if go == qdhr.DialogButton.Yes:
    conn = dialog.Launch()

    # don't allow the connection to close itself so we can expect that it will be valid
    # when the delayed callback below is called
    conn.PreventAutoClose()

    def connected_cb():
        print(f"Connected to {conn.Target()} running APIs: {', '.join(conn.GetAPIs())}")

        numcaps = len(conn.GetCaptures())
        if numcaps == 0:
            print("No captures have been made!")
        else:
            print(f"{numcaps} captures have been made!")

    # wait a little bit, then call our callback to print the connection status
    pydhr.DelayedCallback(5000, connected_cb)
