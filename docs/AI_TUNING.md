# AI Tuning

Canonical design source: `PRODUCTION_PACKAGE.md` §5. Implemented in Milestone 5.

## Fairness contract (tested)

| Rule (spec §5) | How it is enforced | Test |
|---|---|---|
| React only to information a human can see | The AI receives only `AIObservation` snapshots: positions, facing, visible action/animation and its frame, hit-spark (connected), health, combo counter. No buffers, held buttons, stun counters, chains or inputs. | `test_observation_exposes_only_visible_information` |
| Configurable reaction delay; no future input | The whole screen (opponent **and itself**) is seen `reaction_delay_ticks` late. The controller keeps only the delayed snapshot and one older one (velocity). | `test_ai_perception_is_exactly_reaction_delay_old`, `test_ai_does_not_read_future_input` |
| Don't bypass startup/recovery/hit detection | Output is a plain `FighterInputFrame`, the same as a player's; the simulation enforces every rule. Replaying the AI's inputs as a "human" gives the identical fight. | `test_ai_actions_are_legal_player_actions` |
| Difficulty only via reaction, decisions, move choice | `AIProfile` has no damage/health/speed/frame-data/meter knobs (checked by property name). | `test_profiles_valid_and_only_skill_knobs` |
| Never idle permanently | Anti-idle forces approach/attack after `max_idle_ticks`; every AI beats a passive opponent. | `test_ai_never_idles_permanently` |
| Deterministic, debuggable | Seeded RNG; per-AI decision log (state, action, reason, tick) on the debug panel and stdout in debug builds. | `test_ai_is_deterministic_and_logs_decisions` |

Two leaks were found by these tests during development and fixed: the AI
originally saw its own state without delay (so P1's input could reach it
early through its own body), and the spacing projection read one snapshot
newer than allowed.

## States

`NEUTRAL, APPROACH, RETREAT, ATTACK, BLOCK, PUNISH, RECOVER, STUNNED,
KNOCKDOWN, WAKEUP` — KNOCKDOWN is used for KO; WAKEUP is reserved until
knockdowns exist.

Per tick, on the delayed snapshot: stunned → hold block / mash Light (in
range) · attacking → follow the committed combo route on contact · neutral →
block a visible threat (rolled once per attack) → punish visible recovery
(rolled once) → guard window → periodic decision (approach / attack by
weighted choice of in-range moves / guard / retreat / wait) → anti-idle.

Distance bands come from the fighter's own move ranges: **CLOSE** (Light
reaches), **MID** (Kick/Heavy reach), **FAR**.

## Profiles (`data/ai/*.tres`)

| Knob | Beginner | Standard | Expert |
|---|---|---|---|
| Reaction delay (ticks) | 20 | 10 | 5 |
| Decision interval (ticks) | 24 | 12 | 6 |
| Anticipation (spacing) | 0 | 0.7 | 1.0 |
| Aggression | 0.45 | 0.55 | 0.6 |
| Close-range Light bias | 1× | 2× | 3× |
| Range mistakes | 35 % | 5 % | 0 % |
| Combo commit (L, L, K) | 0 % | 50 % | 95 % |
| Block on reaction | 15 % | 60 % | 90 % |
| Pre-emptive guard | 8 % | 35 % | 35 % (+adaptive) |
| Punish visible recovery | 10 % (Light) | 55 % (Light) | 95 % (best damage) |
| Mash Light out of stun | 0 % | 60 % | 60 % |
| Style | predictable walk-in → attack → back-off cycle | balanced | adaptive (guards more vs aggressive opponents, attacks less into blockers) |
| Anti-idle after (ticks) | 90 | 60 | 45 |

What the reaction delays mean with Kairo's moves: Expert (5) can block a
kick (9f) or heavy (12f) on reaction, Standard (10) only the heavy, Beginner
(20) nothing — lower levels rely on guessing (guard).

## Benchmark (`godot --headless --path . --script res://tools/ai_benchmark.gd`)

Seeded AI-vs-AI, 30 s rounds, best of three, 10 matches each (M5 values):

| Match-up | Result |
|---|---|
| Standard vs Beginner | Standard 10–0 |
| Expert vs Beginner | Expert 10–0 |
| Expert vs Standard | Expert 10–0 |

Scripted stand-ins (tests): a walk-in L, L, K "rushdown" script beats
Beginner and Standard; Expert beats it nearly always (it lost 1 of 8 during
tuning). A "turtle" (hold block, punish) beats Beginner and loses to the
others.

**Needs playtests:** these numbers are machine-vs-machine. How each level
feels against a real person on a phone is unverified; Standard in particular
may be too easy against strong pressure.
