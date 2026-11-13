"""Runtime: context, state machine states, tick; the public API seam.

Behavior is defined by docs/decisions.md; summary of the contract below.
"""

from __future__ import annotations

import builtins
from copy import deepcopy
from fractions import Fraction

from . import constants
from .errors import EvaluationError
from .evaluator import BUILTINS_KEY, compile_expr, eval_expr, names_used
from .model import Model
from .scheduler import build_schedule, due_items
from .trace import TraceEvent, TraceSink


class Engine:
    """Executes a Model deterministically.

    Construction (``Engine(model, trace=None)``):
      * Compiles every equation and transition-row equation once with
        evaluator.compile_expr (code objects live on the Engine, not the
        Model) and builds the schedule with scheduler.build_schedule.
      * Context dict initialised with: every input at its InputDef.default;
        every result_variable (standalone and SM rows) = False; every state
        machine name = its default_state; tick = 0; t = Fraction(0);
        dt = Fraction(0) (overwritten per item before evaluation).
      * Nothing is logged at construction.

    step():
      1. tick += 1; ctx["tick"] = tick; ctx["t"] = Fraction(tick - 1) * 1000
         / tick_hz: absolute simulation time in MILLISECONDS (exact, never
         accumulated); the first step is t = 0.
      2. For each item in scheduler.due_items(schedule, tick), in order, set
         ctx["dt"] = 1000 / item.band_hz (milliseconds since the item's
         previous run; on its first run the ideal delta as if it were the
         second run, so dt is always the item's period in ms), then:
         * equation: value = eval_expr(code, ctx); if value != previous,
           store it and emit TraceEvent(component=constants.EQUATIONS_COMPONENT,
           action=f"{name} {old}->{new}", values=used names).
         * state machine (one unit): evaluate ALL rows of ALL transitions
           (no short-circuit), transitions in model order, rows in model
           order; each row's result is written to the context immediately
           (visible to later rows) and a change is logged with component =
           SM name, action = f"{result_variable} {old}->{new}". Then the
           first transition (model order) whose current_state is None or
           equals the current state and whose rows are all True wins; at
           most one fires. If it is global and next_state == current state
           it is a no-op (not logged) and still ends the selection. Otherwise
           ctx[SM name] = next_state (visible immediately) and a TraceEvent is
           emitted with component = SM name, action =
           f'{label} {old}->{new} "{title}"' where label is the transition id,
           prefixed with "T" when the id starts with a digit, and title is
           Transition.title. A non-global self-transition (current ==
           next) fires and is logged.
         * values for all events = sorted (name, ctx value) pairs for the
           names used by the expression(s) involved (all rows of the winning
           transition for a state change) that exist in the context.

    Actions (actions CSV; docs/decisions.md Part C): when a transition fires,
    its exit action runs first (state still the old one), then the state
    changes and the transition is logged, then its entry action runs (state
    already the new one). When no transition fires (a global self-transition
    counts as none), the current state's during action runs. On a machine's
    first pass its master init_action, if any, runs before the transitions
    are evaluated. An action runs its statements in order with exec() on the
    context; each changed target is logged with component = SM name, action =
    f"{action}: set {var} {old!r}->{new!r}". Statements are not type-checked
    or clamped to min/max.

    Expressions are evaluated with the context dict as eval globals
    (``__builtins__`` is stored in it once and excluded from snapshots and
    trace values). A runtime error in an expression is raised as
    EvaluationError (source, tick, item; original chained).

    set_input(name, value): KeyError if ``name`` is not a declared input.
    Sets ctx[name] = value (no type coercion) and always emits TraceEvent at
    the current tick/t with component = constants.INPUT_COMPONENT, action =
    f"set {name} {old!r}->{value!r}", values = ((name, value),).

    Structured fields (TraceEvent.kind etc., for the timeline; the text line
    above does not change): input events have kind="input", name, old, new;
    result changes kind="result" with name = result variable; state changes
    kind="transition" with name = SM name, old/new states, label, title;
    action writes kind="action" with name = target, label = action name and
    phase "init", "exit", "entry" or "during". ``trigger`` (sorted) = the
    names read by the item (the equation; for a state machine the row, or
    for a transition all rows of that transition) whose value differs
    (``!=`` or a different type) from the item's last-seen copy: the values
    at the end of its previous run (the initial context before its first
    run), so it is exact across bands. ``t``, ``tick``, ``dt`` and a machine's
    own name are never triggers; inputs and actions have none. The transition
    trigger is captured with its values, before the exit action. This
    bookkeeping runs only when a trace sink is attached.
    """

    def __init__(self, model: Model, trace: TraceSink | None = None) -> None:
        self._model = model
        self._trace = trace
        self._tick = 0
        self._t = Fraction(0)
        self._schedule = build_schedule(model)
        self._tick_hz = Fraction(model.tick_hz)
        self._eqs = {}
        for eq in model.equations:
            code = compile_expr(eq.equation, eq.source)
            self._eqs[eq.result_variable] = (code, names_used(code), eq.source)
        self._sms = {}
        for sm in model.state_machines:
            trans = []
            for tr in sm.transitions:
                rows = []
                for r in tr.rows:
                    code = compile_expr(r.equation, r.source)
                    rows.append((r.result_variable, code, names_used(code), r.source))
                used = tuple(sorted({n for _, _, ns, _ in rows for n in ns}))
                label = tr.id
                if label[:1].isdigit():
                    label = "T" + label
                trans.append((tr, label, rows, used))
            self._sms[sm.name] = trans
        self._inputs = {i.name for i in model.inputs}
        self._input_names = sorted(self._inputs)
        self._result_names = sorted(
            [e.result_variable for e in model.equations]
            + [r.result_variable for sm in model.state_machines
               for tr in sm.transitions for r in tr.rows]
        )
        self._sm_names = sorted(sm.name for sm in model.state_machines)
        # Actions: name -> [(code, targets, used names, source)] in run order.
        self._actions = {}
        for a in model.actions:
            stmts = []
            for st in a.statements:
                code = compile(st.statement.strip(), st.source, "exec")
                used = tuple(sorted(set(names_used(code)) | set(st.targets)))
                stmts.append((code, st.targets, used, st.source))
            self._actions[a.name] = stmts
        self._sm_defs = {sm.name: sm for sm in model.state_machines}
        self._sm_started: set[str] = set()
        ctx: dict = {}
        for i in model.inputs:
            ctx[i.name] = i.default
        for n in self._result_names:
            ctx[n] = False
        for sm in model.state_machines:
            ctx[sm.name] = sm.default_state
        ctx["tick"] = 0
        ctx["t"] = Fraction(0)
        ctx["dt"] = Fraction(0)
        ctx[BUILTINS_KEY] = builtins
        self._ctx = ctx
        # Trigger bookkeeping (used only when a trace sink is attached):
        # names each item reads (no t/tick/dt/builtins, no SM's own name) and
        # the item's last-seen copy of them, initially the starting context.
        skip = {"t", "tick", "dt", BUILTINS_KEY}

        def reads(names, own=None):
            return tuple(n for n in sorted(set(names))
                         if n in ctx and n not in skip and n != own)

        self._eq_reads = {rv: reads(used) for rv, (_c, used, _s) in self._eqs.items()}
        self._row_reads = {}  # (sm, row source) -> names
        self._tr_reads = {}  # id(transition) -> names
        self._sm_reads = {}
        for name, trans in self._sms.items():
            all_names = set()
            for tr, _label, rows, used in trans:
                for _rv, _code, row_used, src in rows:
                    self._row_reads[(name, src)] = reads(row_used, name)
                self._tr_reads[id(tr)] = reads(used, name)
                all_names.update(used)
            self._sm_reads[name] = reads(all_names, name)
        self._eq_seen = {rv: {n: ctx[n] for n in ns} for rv, ns in self._eq_reads.items()}
        self._sm_seen = {sm: {n: ctx[n] for n in ns} for sm, ns in self._sm_reads.items()}

    @property
    def tick(self) -> int:
        """Number of completed steps (0 before the first step)."""
        return self._tick

    @property
    def t(self) -> Fraction:
        """Absolute simulation time in milliseconds of the latest step:
        Fraction(tick - 1) * 1000 / model.tick_hz (0 before and at the first step)."""
        return self._t

    def _vals(self, names) -> tuple:
        ctx = self._ctx
        return tuple((n, ctx[n]) for n in sorted(set(names)) if n in ctx and n != BUILTINS_KEY)

    def _emit(self, component: str, action: str, values: tuple, **fields) -> None:
        if self._trace is not None:
            self._trace.emit(TraceEvent(self._tick, self._t, component, action, values,
                                        **fields))

    def _trigger(self, names, seen: dict) -> tuple:
        """The names (already sorted) whose context value differs from ``seen``."""
        ctx = self._ctx
        out = []
        for n in names:
            a, b = ctx[n], seen[n]
            if a != b or type(a) is not type(b):
                out.append(n)
        return tuple(out)

    @staticmethod
    def _remember(seen: dict, ctx: dict) -> None:
        for n in seen:
            seen[n] = ctx[n]

    def _eval(self, code, source: str, item: str) -> bool:
        try:
            return eval_expr(code, self._ctx)
        except Exception as exc:
            raise EvaluationError(source, self._tick, item, exc) from exc

    def step(self) -> None:
        """Advance one tick and run every due item (see class docstring)."""
        ctx = self._ctx
        self._tick += 1
        self._t = Fraction(self._tick - 1) * 1000 / self._tick_hz
        ctx["tick"] = self._tick
        ctx["t"] = self._t
        for item in due_items(self._schedule, self._tick):
            ctx["dt"] = 1000 / item.band_hz
            if item.kind == "equation":
                code, used, src = self._eqs[item.name]
                new = self._eval(code, src, item.name)
                old = ctx[item.name]
                if new != old:
                    ctx[item.name] = new
                    if self._trace is not None:
                        self._emit(constants.EQUATIONS_COMPONENT,
                                   f"{item.name} {old}->{new}", self._vals(used),
                                   kind="result", name=item.name, old=old, new=new,
                                   trigger=self._trigger(self._eq_reads[item.name],
                                                         self._eq_seen[item.name]))
                if self._trace is not None:
                    self._remember(self._eq_seen[item.name], ctx)
            else:
                self._run_sm(item.name)

    def _run_action(self, sm: str, action: str, phase: str) -> None:
        """Run the statements of ``action`` in order; log each changed target
        under the state machine's name."""
        ctx = self._ctx
        for code, targets, used, src in self._actions[action]:
            old = [ctx[n] for n in targets]
            try:
                exec(code, ctx)
            except Exception as exc:
                raise EvaluationError(src, self._tick, sm, exc) from exc
            for n, before in zip(targets, old):
                if ctx[n] != before or type(ctx[n]) is not type(before):
                    self._emit(sm, f"{action}: set {n} {before!r}->{ctx[n]!r}",
                               self._vals(used), kind="action", name=n, old=before,
                               new=ctx[n], label=action, phase=phase)

    def _run_sm(self, name: str) -> None:
        self._run_sm_pass(name)
        if self._trace is not None:
            self._remember(self._sm_seen[name], self._ctx)

    def _run_sm_pass(self, name: str) -> None:
        if name not in self._sm_started:
            self._sm_started.add(name)
            init = self._sm_defs[name].init_action
            if init:
                self._run_action(name, init, "init")
        fired = self._select(name)
        if fired is None:
            during = self._sm_defs[name].during_action(self._ctx[name])
            if during:
                self._run_action(name, during, "during")
            return
        tr, label, used = fired
        ctx = self._ctx
        cur = ctx[name]
        values = self._vals(used)  # the values that made the transition fire
        trigger = ()
        if self._trace is not None:
            trigger = self._trigger(self._tr_reads[id(tr)], self._sm_seen[name])
        if tr.exit_action:
            self._run_action(name, tr.exit_action, "exit")
        ctx[name] = tr.next_state
        self._emit(name, f'{label} {cur}->{tr.next_state} "{tr.title}"', values,
                   kind="transition", name=name, old=cur, new=tr.next_state,
                   label=label, title=tr.title, trigger=trigger)
        if tr.entry_action:
            self._run_action(name, tr.entry_action, "entry")

    def _select(self, name: str):
        """Evaluate every row; return (transition, label, used names) of the
        transition that fires, or None when none does (including a global
        self-transition, which wins the pass but changes nothing)."""
        ctx = self._ctx
        trans = self._sms[name]
        results = []
        for tr, _label, rows, _used in trans:
            ok = True
            for rv, code, used, src in rows:
                new = self._eval(code, src, name)
                old = ctx[rv]
                if new != old:
                    ctx[rv] = new
                    if self._trace is not None:
                        self._emit(name, f"{rv} {old}->{new}", self._vals(used),
                                   kind="result", name=rv, old=old, new=new,
                                   trigger=self._trigger(self._row_reads[(name, src)],
                                                         self._sm_seen[name]))
                if not new:
                    ok = False
            results.append(ok)
        cur = ctx[name]
        for (tr, label, rows, used), ok in zip(trans, results):
            if tr.current_state is not None and tr.current_state != cur:
                continue
            if not ok:
                continue
            if tr.current_state is None and tr.next_state == cur:
                return None  # global self-transition: no-op, still wins
            return tr, label, used
        return None

    def run(self, ticks: int) -> None:
        """Call step() ``ticks`` times (0 is a no-op); ValueError if negative."""
        if ticks < 0:
            raise ValueError(f"ticks must be >= 0, got {ticks}")
        for _ in range(ticks):
            self.step()

    def snapshot(self) -> dict:
        """Return a fresh, independent (deep-copied) dict; ``t`` is float ms."""
        ctx = self._ctx
        return {
            "tick": self._tick,
            "t": float(self._t),  # milliseconds
            "states": deepcopy({n: ctx[n] for n in self._sm_names}),
            "outputs": deepcopy({n: ctx[n] for n in self._result_names}),
            "inputs": deepcopy({n: ctx[n] for n in self._input_names}),
        }

    def set_input(self, name: str, value: object) -> None:
        """Write an external input. KeyError if unknown."""
        if name not in self._inputs:
            raise KeyError(name)
        old = self._ctx[name]
        self._ctx[name] = value
        self._emit(constants.INPUT_COMPONENT, f"set {name} {old!r}->{value!r}",
                   ((name, value),), kind="input", name=name, old=old, new=value)
