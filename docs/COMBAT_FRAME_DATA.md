# Combat Frame Data

Canonical design source: `PRODUCTION_PACKAGE.md` §4.3–§4.5. This file holds
the implemented conventions and the current numbers. Updated: Milestone 4.

## Conventions (decision D-018)

- 1 frame = 1 combat tick at **60 Hz** (16.67 ms). Never render frames.
- **Startup includes the first active frame** (fighting-game standard): a 5f
  move shows its hitbox on frame 5.
- Total duration = startup + active − 1 + recovery.
- Advantage (contact on the first active frame):
  - on hit  = hitstun − (active − 1 + recovery)
  - on block = blockstun − (active − 1 + recovery)
- A stun of N means N full ticks without control; the fighter acts on tick N+1.
- Hitstop freezes **both** fighters equally, so it never changes advantage.
- A move is punishable on block by a move with startup ≤ −(block advantage),
  if still in range after pushback.

## Rules

| Rule | Implementation |
|---|---|
| Hit detection | Rect overlap on the fighting plane, sampled once per tick after movement (D-017). |
| One hit per attack | `move_connected` set on hit or block; hitbox can't connect again. |
| Block | Hold BLOCK in a neutral state. Blocks HIGH, MID, PROJECTILE. LOW needs crouch-block, THROW can't be blocked (both arrive later; no such moves exist yet). Attacking fighters cannot block. |
| Damage | Hit: `damage`. Block: `chip_damage`; chip **can** KO. |
| Trades | All contacts in a tick are judged on the pre-resolution state → both fighters get hit. No clash/priority system. |
| Interrupts | Getting hit cancels the defender's own attack (startup or recovery). |
| Pushback | Defender slides `pushback` m over 6 ticks after hitstop. If the wall stops it, the attacker slides back instead. |
| Hitstop | Global; length = largest `hitstop_frames` among the tick's contacts. Presses during hitstop are latched. |
| Facing | Only neutral fighters turn; attacks/stuns keep their facing. |
| KO | Health 0 → KO state, no hurtbox, input ignored. Training reset (R / F5 / Reset button) restores. |
| Attack priority | Several attack buttons pressed on the same tick: Heavy > Kick > Light. |
| Input buffer | Attack presses are buffered for **6 ticks** (`data/rules/combat_tuning.tres`). Buffer age does not advance during hitstop. The newest legal press is used; illegal ones stay buffered until they expire. Block is a held state, never buffered. |
| Cancels | Allowed only on contact (hit **or** block), from the first active frame until **3 frames** after the last active frame, into a move whose `tags` appear in the current move's `cancel_tags`, and only if that move is in the current chain fewer than **2** times. |
| Combo | Counted on the defender: a hit while the defender is already in HITSTUN is the next hit of the combo. Ends when the defender recovers to neutral, or when an attack is blocked. |
| Combo scaling | Damage % by hit number: 100, 100, 80, 70, 60, 50, then 40 (integer maths, min 1 damage). Chip is never scaled. |

## Kairo (placeholder) — prototype values

| Move | Startup | Active | Recovery | Total | Damage | Chip | Hitstun | Blockstun | On hit | On block | Hitstop | Pushback | Level | Reach* |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Light punch | 5 | 3 | 10 | 17 | 35 | 0 | 14 | 11 | **+2** | **−1** | 6 | 0.25 m | High | 1.15 m |
| Heavy punch | 12 | 3 | 19 | 33 | 85 | 8 | 24 | 16 | **+3** | **−5** | 11 | 0.20 m | Mid | 1.30 m |
| Kick | 9 | 4 | 15 | 27 | 60 | 4 | 20 | 15 | **+2** | **−3** | 8 | 0.40 m | Mid | 1.45 m |

\*Reach = maximum centre-to-centre distance at which the move can hit a
standing Kairo-sized hurtbox (half-width 0.3 m).

Startup/active/recovery/damage are the spec §4.4 starting values. Stun,
hitstop, pushback, chip and hitboxes are first-pass values; all are
playtest-tunable in `data/moves/*.tres`. Tests check the advantage numbers
above against the live simulation, so changing data cannot silently break
them.

Notable consequence: heavy is −5 on block and punishable by the 5f light at
close range (≤ ~0.95 m); from further out its pushback leaves the light out
of reach.

## Cancel routes (Kairo placeholder)

| Move | tags | cancel_tags (can cancel into) |
|---|---|---|
| Light punch | normal, light | light, kick |
| Heavy punch | normal, heavy | special *(no specials yet)* |
| Kick | normal, kick | special *(no specials yet)* |

Rejected (tested): Light→Heavy, Kick→Light, Heavy→Light, any cancel on whiff,
any cancel after the window, a third Light in one chain.

**Starter route (spec §4.5): Light, Light, Kick** = 3 hits,
35 + 35 + 48 (kick at 80 %) = **118 damage**. It connects from up to
**0.94 m** apart (mid-screen or corner) when each cancel is input as early
as possible — the first Light's pushback otherwise carries the dummy out of
Light range. Origin Palm and the heavy follow-up join the route in M6.

## Infinite-combo guarantee

`test_no_infinite_combo_exhaustive_routes` tries all 363 routes of 1–5
attacks from {L, K, H}, each mashed so every cancel and every link is
attempted, mid-screen and cornered, standing and walking forward (1,452
runs). The longest combo found is 3 hits and the defender always recovers.
Bounds come from: tag routes ending at Kick/Heavy, the 2-per-chain repeat
limit, pushback, and no move being plus enough to link into itself.
