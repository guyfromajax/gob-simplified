"""``GOB_STRICT_EXCEPTIONS`` — make a programming error loud in tests, silent in production.

**Default OFF.** An unset flag is today's behaviour, exactly. This is the opposite default
from ``GOB_DEFENDER_AG_SPREAD``; do not copy that flag's ``"1"`` idiom here.

WHY THIS EXISTS
    The animation / step-emission path carries 66 ``except Exception`` handlers
    (reports/rebaseline-and-handler-audit.md). During Stage 2 a ``NameError`` in
    ``shot_micro_movements.build_shot_micro_steps`` fired 70-101 times per game and was
    caught by ``turn_manager.py:4107``, which logged a warning and let the turn continue
    with **no animation_steps at all**. The equiv-v3 harness discarded the log, so the only
    thing that noticed was the reference run, several hours later.

    Those handlers are not wrong: they keep the sim alive when an emitter fails on a rare
    turn, and the census found nothing legitimate depending on them only because 8 games
    never hit such a turn. So this does **not** narrow or remove any of them. It is purely
    additive: with the flag on, a handler re-raises the four exception types that are
    always programming errors and never an expected condition.

WHAT IT DOES NOT DO
    * It does not change which types a handler catches.
    * It raises nothing of its own. If it cannot read the flag it returns, and the handler
      behaves exactly as it does today.
    * With the flag off it is a type check and a dict lookup on a path that, per the
      census, executes ~0 times per game.

THE FLAG IS READ AT CALL TIME, NOT AT IMPORT
    Deliberately. These handlers only run when an exception has already fired, so there is
    no hot path to optimise, and an import-time constant could not be monkeypatched by a
    test. ``conftest.py`` sets the flag for the whole suite, and the equiv-v3 runner sets
    it too, so a typo'd name fails loudly in both places instead of silently emitting a
    turn with no animation.
"""

import os

#: The environment variable. Unset or anything other than "1" means OFF.
STRICT_EXCEPTIONS_FLAG = "GOB_STRICT_EXCEPTIONS"

#: Exception types that are always a bug in our own code, never an expected condition.
#: ``UnboundLocalError`` is a subclass of ``NameError`` and is named for clarity.
STRICT_EXCEPTION_TYPES = (NameError, AttributeError, TypeError, UnboundLocalError)


def strict_exceptions_enabled() -> bool:
    """``GOB_STRICT_EXCEPTIONS`` — **default OFF**. Read at call time so tests can set it."""
    return os.environ.get(STRICT_EXCEPTIONS_FLAG, "0") == "1"


def reraise_if_strict(exc: BaseException) -> None:
    """Re-raise ``exc`` when it is a programming error and strict mode is on; else return.

    Call this as the FIRST statement of a broad ``except Exception as e:`` handler::

        except Exception as e:
            reraise_if_strict(e)
            logging.warning("emitter failed: %s", e)

    Guarantees, in order of how much they matter:

    1. **It never raises anything of its own.** Any failure inside it (a weird ``exc``, a
       missing environ) returns, leaving the handler to do what it does today.
    2. **It never swallows.** It either re-raises the caller's own exception or returns.
    3. Re-raising ``exc`` preserves the original traceback, so the report names the real
       site rather than this helper.
    """
    try:
        if not isinstance(exc, STRICT_EXCEPTION_TYPES):
            return
        if not strict_exceptions_enabled():
            return
    except Exception:
        # A guard that corrects must not become the fault. Anything unexpected here means
        # the handler proceeds exactly as it would without strict mode.
        return
    raise exc
