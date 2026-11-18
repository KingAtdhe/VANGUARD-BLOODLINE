# Combat Frame Data

Canonical design source: `PRODUCTION_PACKAGE.md` §4.3–§4.5. This file holds
the implemented conventions and the current numbers. Updated: Milestone 2.

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
