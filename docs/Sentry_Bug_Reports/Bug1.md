# ImportError: cannot import name 'DEFENDER_X_OFFSET' from 'BackEnd.constants.fast_break_constants' (/app/BackEnd/constants/fast_break_constants.py)

**Issue ID:** 7245968237
**Project:** python-fastapi
**Date:** 2/5/2026, 8:36:18 PM
## Issue Summary
Missing Constant: DEFENDER_X_OFFSET during Uvicorn Load
**What's wrong:** **ImportError** on `DEFENDER_X_OFFSET` from **`fast_break_constants.py`**.
**In the trace:** The error originates during **Uvicorn startup** loading the **ASGI app**.
**Possible cause:** The constant `DEFENDER_X_OFFSET` was **recently removed or renamed** in `fast_break_constants.py`.

## Tags

- **environment:** gob-backend-staging
- **handled:** no
- **level:** error
- **mechanism:** excepthook
- **runtime:** CPython 3.12.7
- **runtime.name:** CPython
- **server_name:** ac05d2398304

## Exception

### Exception 1
**Type:** ImportError
**Value:** cannot import name 'DEFENDER_X_OFFSET' from 'BackEnd.constants.fast_break_constants' (/app/BackEnd/constants/fast_break_constants.py)

#### Stacktrace

```
 <module> in BackEnd/constants/__init__.py [Line 291] (In app)
    "GUARD_BALL": "guard_ball",
    "GUARD_OFFBALL": "guard_offball"
}

# Import fast break constants
from BackEnd.constants.fast_break_constants import (  <-- SUSPECT LINE
    BALL_HANDLER_MOVE_X_MIN,
    BALL_HANDLER_MOVE_X_MAX,
    BALL_HANDLER_MOVE_Y_RANGE,
    STOPPER_OFFSET_MIN,
    STOPPER_OFFSET_MAX,
---
Variable values:
{
  "__builtins__": {
    "__build_class__": "<built-in function __build_class__>",
    "__doc__": "\"Built-in functions, types, exceptions, and other objects.\\n\\nThis module provides direct access to all 'built-in'\\nidentifiers of Python; for example, builtins.len is\\nthe full name for the built-in function len().\\n\\nThis module is not normally accessed explicitly by most\\napplications, but can be useful in modules that provide\\nobjects with the same name as a built-in value, but in\\nwhich the built-in of that name is also needed.\"",
    "__import__": "<built-in function __import__>",
    "__loader__": "<class '_frozen_importlib.BuiltinImporter'>",
    "__name__": "'builtins'",
    "__package__": "''",
    "__spec__": "ModuleSpec(name='builtins', loader=<class '_frozen_importlib.BuiltinImporter'>, origin='built-in')",
    "abs": "<built-in function abs>",
    "all": "<built-in function all>",
    "any": "<built-in function any>"
  },
  "__cached__": "'/app/BackEnd/constants/__pycache__/__init__.cpython-312.pyc'",
  "__doc__": "None",
  "__file__": "'/app/BackEnd/constants/__init__.py'",
  "__loader__": "<_frozen_importlib_external.SourceFileLoader object at 0x7f9bae4f2810>",
  "__name__": "'BackEnd.constants'",
  "__package__": "'BackEnd.constants'",
  "__path__": [
    "'/app/BackEnd/constants'"
  ],
  "__spec__": "ModuleSpec(name='BackEnd.constants', loader=<_frozen_importlib_external.SourceFileLoader object at 0x7f9bae4f2810>, origin='/app/BackEnd/constants/__init__.py', submodule_search_locations=['/app/BackEnd/constants'])",
  "random": "<module 'random' from '/root/.nix-profile/lib/python3.12/random.py'>"
}

=======
 <module> in BackEnd/api/api.py [Line 24] (In app)
from fastapi import Depends, FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi import Request
from BackEnd.constants import POSITION_LIST  <-- SUSPECT LINE
import uuid
from BackEnd.main import run_simulation, simulate_quarter
from BackEnd.models.game_manager import GameManager
# ✅ PERFORMANCE: Removed debug print statements
from BackEnd.db import (
---
Variable values:
{
  "__annotations__": {},
  "__builtins__": {
    "__build_class__": "<built-in function __build_class__>",
    "__doc__": "\"Built-in functions, types, exceptions, and other objects.\\n\\nThis module provides direct access to all 'built-in'\\nidentifiers of Python; for example, builtins.len is\\nthe full name for the built-in function len().\\n\\nThis module is not normally accessed explicitly by most\\napplications, but can be useful in modules that provide\\nobjects with the same name as a built-in value, but in\\nwhich the built-in of that name is also needed.\"",
    "__import__": "<built-in function __import__>",
    "__loader__": "<class '_frozen_importlib.BuiltinImporter'>",
    "__name__": "'builtins'",
    "__package__": "''",
    "__spec__": "ModuleSpec(name='builtins', loader=<class '_frozen_importlib.BuiltinImporter'>, origin='built-in')",
    "abs": "<built-in function abs>",
    "all": "<built-in function all>",
    "any": "<built-in function any>"
  },
  "__cached__": "'/app/BackEnd/api/__pycache__/api.cpython-312.pyc'",
  "__doc__": "None",
  "__file__": "'/app/BackEnd/api/api.py'",
  "__loader__": "<_frozen_importlib_external.SourceFileLoader object at 0x7f9bafd6a420>",
  "__name__": "'BackEnd.api.api'",
  "__package__": "'BackEnd.api'",
  "__spec__": "ModuleSpec(name='BackEnd.api.api', loader=<_frozen_importlib_external.SourceFileLoader object at 0x7f9bafd6a420>, origin='/app/BackEnd/api/api.py')",
  "re": "<module 're' from '/root/.nix-profile/lib/python3.12/re/__init__.py'>"
}

=======
 _call_with_frames_removed in <frozen importlib._bootstrap> [Line 488] (In app)
---
Variable values:
{
  "args": [
    "<code object <module> at 0x14366e10, file \"/app/BackEnd/api/api.py\", line 1>",
    {
      "__annotations__": {},
      "__builtins__": {
        "__build_class__": "<built-in function __build_class__>",
        "__doc__": "\"Built-in functions, types, exceptions, and other objects.\\n\\nThis module provides direct access to all 'built-in'\\nidentifiers of Python; for example, builtins.len is\\nthe full name for the built-in function len().\\n\\nThis module is not normally accessed explicitly by most\\napplications, but can be useful in modules that provide\\nobjects with the same name as a built-in value, but in\\nwhich the built-in of that name is also needed.\"",
        "__import__": "<built-in function __import__>",
        "__loader__": "<class '_frozen_importlib.BuiltinImporter'>",
        "__name__": "'builtins'",
        "__package__": "''",
        "__spec__": "ModuleSpec(name='builtins', loader=<class '_frozen_importlib.BuiltinImporter'>, origin='built-in')",
        "abs": "<built-in function abs>",
        "all": "<built-in function all>",
        "any": "<built-in function any>"
      },
      "__cached__": "'/app/BackEnd/api/__pycache__/api.cpython-312.pyc'",
      "__doc__": "None",
      "__file__": "'/app/BackEnd/api/api.py'",
      "__loader__": "<_frozen_importlib_external.SourceFileLoader object at 0x7f9bafd6a420>",
      "__name__": "'BackEnd.api.api'",
      "__package__": "'BackEnd.api'",
      "__spec__": "ModuleSpec(name='BackEnd.api.api', loader=<_frozen_importlib_external.SourceFileLoader object at 0x7f9bafd6a420>, origin='/app/BackEnd/api/api.py')",
      "re": "<module 're' from '/root/.nix-profile/lib/python3.12/re/__init__.py'>"
    }
  ],
  "f": "<built-in function exec>",
  "kwds": {}
}

=======
 exec_module in <frozen importlib._bootstrap_external> [Line 995] (In app)
---
Variable values:
{
  "code": "<code object <module> at 0x14366e10, file \"/app/BackEnd/api/api.py\", line 1>",
  "module": "<module 'BackEnd.api.api' from '/app/BackEnd/api/api.py'>",
  "self": "<_frozen_importlib_external.SourceFileLoader object at 0x7f9bafd6a420>"
}

=======
 _load_unlocked in <frozen importlib._bootstrap> [Line 935] (In app)
---
Variable values:
{
  "module": "<module 'BackEnd.api.api' from '/app/BackEnd/api/api.py'>",
  "spec": "ModuleSpec(name='BackEnd.api.api', loader=<_frozen_importlib_external.SourceFileLoader object at 0x7f9bafd6a420>, origin='/app/BackEnd/api/api.py')"
}

=======
 _find_and_load_unlocked in <frozen importlib._bootstrap> [Line 1331] (In app)
---
Variable values:
{
  "child": "'api'",
  "import_": "<function _gcd_import at 0x7f9bb0e180e0>",
  "name": "'BackEnd.api.api'",
  "parent": "'BackEnd.api'",
  "parent_module": "<module 'BackEnd.api' (namespace) from ['/app/BackEnd/api']>",
  "parent_spec": "ModuleSpec(name='BackEnd.api', loader=<_frozen_importlib_external.NamespaceLoader object at 0x7f9bafd69f70>, submodule_search_locations=_NamespacePath(['/app/BackEnd/api']))",
  "path": "_NamespacePath(['/app/BackEnd/api'])",
  "spec": "ModuleSpec(name='BackEnd.api.api', loader=<_frozen_importlib_external.SourceFileLoader object at 0x7f9bafd6a420>, origin='/app/BackEnd/api/api.py')"
}

=======
 _find_and_load in <frozen importlib._bootstrap> [Line 1360] (In app)
---
Variable values:
{
  "import_": "<function _gcd_import at 0x7f9bb0e180e0>",
  "module": "<object object at 0x7f9bb0df0060>",
  "name": "'BackEnd.api.api'"
}

=======
 _gcd_import in <frozen importlib._bootstrap> [Line 1387] (In app)
---
Variable values:
{
  "level": "0",
  "name": "'BackEnd.api.api'",
  "package": "None"
}

=======
 import_module in __init__.py [Line 90] (Not in app)
                            f"relative import for {name!r}")
        for character in name:
            if character != '.':
                break
            level += 1
    return _bootstrap._gcd_import(name[level:], package, level)  <-- SUSPECT LINE


_RELOADING = {}


---
Variable values:
{
  "level": "0",
  "name": "'BackEnd.api.api'",
  "package": "None"
}

=======
 import_from_string in uvicorn/importer.py [Line 19] (Not in app)
    if not module_str or not attrs_str:
        message = 'Import string "{import_str}" must be in format "<module>:<attribute>".'
        raise ImportFromStringError(message.format(import_str=import_str))

    try:
        module = importlib.import_module(module_str)  <-- SUSPECT LINE
    except ModuleNotFoundError as exc:
        if exc.name != module_str:
            raise exc from None
        message = 'Could not import module "{module_str}".'
        raise ImportFromStringError(message.format(module_str=module_str))
---
Variable values:
{
  "_": "':'",
  "attrs_str": "'app'",
  "import_str": "'BackEnd.api.api:app'",
  "module_str": "'BackEnd.api.api'"
}

=======
 load in uvicorn/config.py [Line 439] (Not in app)
            self.ws_protocol_class = self.ws

        self.lifespan_class = import_from_string(LIFESPAN[self.lifespan])

        try:
            self.loaded_app = import_from_string(self.app)  <-- SUSPECT LINE
        except ImportFromStringError as exc:
            logger.error("Error loading ASGI app. %s" % exc)
            sys.exit(1)

        try:
---
Variable values:
{
  "encoded_headers": [],
  "http_protocol_class": "<class 'uvicorn.protocols.http.h11_impl.H11Protocol'>",
  "self": "<uvicorn.config.Config object at 0x7f9bafcb8350>",
  "ws_protocol_class": "None"
}

=======
 _serve in uvicorn/server.py [Line 78] (Not in app)
    async def _serve(self, sockets: list[socket.socket] | None = None) -> None:
        process_id = os.getpid()

        config = self.config
        if not config.loaded:
            config.load()  <-- SUSPECT LINE

        self.lifespan = config.lifespan_class(config)

        message = "Started server process [%d]"
        color_message = "Started server process [" + click.style("%d", fg="cyan") + "]"
---
Variable values:
{
  "config": "<uvicorn.config.Config object at 0x7f9bafcb8350>",
  "process_id": "1",
  "self": "<uvicorn.server.Server object at 0x7f9bafebd550>",
  "sockets": "None"
}

=======
 serve in uvicorn/server.py [Line 71] (Not in app)
    def run(self, sockets: list[socket.socket] | None = None) -> None:
        return asyncio_run(self.serve(sockets=sockets), loop_factory=self.config.get_loop_factory())

    async def serve(self, sockets: list[socket.socket] | None = None) -> None:
        with self.capture_signals():
            await self._serve(sockets)  <-- SUSPECT LINE

    async def _serve(self, sockets: list[socket.socket] | None = None) -> None:
        process_id = os.getpid()

        config = self.config
---
Variable values:
{
  "self": "<uvicorn.server.Server object at 0x7f9bafebd550>",
  "sockets": "None"
}

=======
 run_until_complete in asyncio/base_events.py [Line 687] (Not in app)
        finally:
            future.remove_done_callback(_run_until_complete_cb)
        if not future.done():
            raise RuntimeError('Event loop stopped before Future completed.')

        return future.result()  <-- SUSPECT LINE

    def stop(self):
        """Stop running the event loop.

        Every callback already scheduled will still run.  This simply informs
---
Variable values:
{
  "future": "<Task finished name='Task-1' coro=<Server.serve() done, defined at /opt/venv/lib/python3.12/site-packages/uvicorn/server.py:69> exception=ImportError(\"cannot import name 'DEFENDER_X_OFFSET' from 'BackEnd.constants.fast_break_constants' (/app/BackEnd/constants/fast_break_constants.py)\")>",
  "new_task": "False",
  "self": "<_UnixSelectorEventLoop running=False closed=True debug=False>"
}

=======
 run in asyncio/runners.py [Line 118] (Not in app)
        else:
            sigint_handler = None

        self._interrupt_count = 0
        try:
            return self._loop.run_until_complete(task)  <-- SUSPECT LINE
        except exceptions.CancelledError:
            if self._interrupt_count > 0:
                uncancel = getattr(task, "uncancel", None)
                if uncancel is not None and uncancel() == 0:
                    raise KeyboardInterrupt()
---
Variable values:
{
  "context": "<_contextvars.Context object at 0x7f9bafd12a00>",
  "coro": "<coroutine object Server.serve at 0x7f9bafccfca0>",
  "self": "<asyncio.runners.Runner object at 0x7f9bafe4e7e0>",
  "sigint_handler": "functools.partial(<bound method Runner._on_sigint of <asyncio.runners.Runner object at 0x7f9bafe4e7e0>>, main_task=<Task finished name='Task-1' coro=<Server.serve() done, defined at /opt/venv/lib/python3.12/site-packages/uvicorn/server.py:69> exception=ImportError(\"cannot import name 'DEFENDER_X_OFFSET' from 'BackEnd.constants.fast_break_constants' (/app/BackEnd/constants/fast_break_constants.py)\")>)",
  "task": "<Task finished name='Task-1' coro=<Server.serve() done, defined at /opt/venv/lib/python3.12/site-packages/uvicorn/server.py:69> exception=ImportError(\"cannot import name 'DEFENDER_X_OFFSET' from 'BackEnd.constants.fast_break_constants' (/app/BackEnd/constants/fast_break_constants.py)\")>"
}

=======
 run in asyncio/runners.py [Line 194] (Not in app)
        # fail fast with short traceback
        raise RuntimeError(
            "asyncio.run() cannot be called from a running event loop")

    with Runner(debug=debug, loop_factory=loop_factory) as runner:
        return runner.run(main)  <-- SUSPECT LINE


def _cancel_all_tasks(loop):
    to_cancel = tasks.all_tasks(loop)
    if not to_cancel:
---
Variable values:
{
  "debug": "None",
  "loop_factory": "<class 'asyncio.unix_events._UnixSelectorEventLoop'>",
  "main": "<coroutine object Server.serve at 0x7f9bafccfca0>",
  "runner": "<asyncio.runners.Runner object at 0x7f9bafe4e7e0>"
}

=======
```
