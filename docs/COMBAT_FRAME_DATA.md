# Combat Frame Data

Canonical design source: `PRODUCTION_PACKAGE.md` §4.3–§4.5. This file holds
the implemented conventions and the current numbers. Updated: Milestone 6.

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
| Block | Hold BLOCK in a neutral state: standing block. Hold DOWN + BLOCK: low block. MID and PROJECTILE are stopped by either; HIGH (overheads) only by a standing block; LOW only by a low block; THROW by neither (throws arrive later). Guard height is read live, also during blockstun. Attacking fighters cannot block. Ordinary punches are MID; HIGH is reserved for overheads. No LOW or HIGH move exists in the shipped data yet (they arrive with the per-fighter move sets). |
| Direction + button | DOWN + LIGHT/HEAVY/KICK/SPECIAL and BACK + SPECIAL are their own input patterns (`DOWN_LIGHT`, `DOWN_HEAVY`, `DOWN_KICK`, `DOWN_SPECIAL`, `BACK_SPECIAL`; FORWARD + SPECIAL as before). Down wins over forward/back. A fighter with no move for the pattern gets the plain button's move. |
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
| Light punch | 5 | 3 | 10 | 17 | 35 | 0 | 14 | 11 | **+2** | **−1** | 6 | 0.25 m | Mid | 1.15 m |
| Heavy punch | 12 | 3 | 19 | 33 | 85 | 8 | 24 | 16 | **+3** | **−5** | 11 | 0.20 m | Mid | 1.30 m |
| Kick (shared set: the other five fighters and bosses) | 9 | 4 | 15 | 27 | 60 | 4 | 20 | 15 | **+2** | **−3** | 8 | 0.40 m | Mid | 1.45 m |
| Low Kick (Kairo, K) | 9 | 4 | 15 | 27 | 50 | 4 | 20 | 15 | **+2** | **−3** | 8 | 0.35 m | Low | 1.45 m |
| Body Hook (Kairo, down + H) | 9 | 3 | 15 | 26 | 55 | 3 | 19 | 13 | **+2** | **−4** | 7 | 0.30 m | Mid | 1.15 m |
| Slip Counter (Kairo, back + SP) | counter window frames 4–16 of 30 | | | 30 | 0 | | | | | | | | catches High, Mid | — |
| Counter Hook (follow-up only) | 5 | 3 | 16 | 23 | 90 | 5 | 22 | 14 | **+4** | **−4** | 10 | 0.45 m | Mid | 1.18 m |

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

## Specials, Surge and ultimate (Milestone 6)

| Move | Input | Startup | Active | Recovery | Total | Damage | Chip | On hit | On block | Meter | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Origin Palm | Special (neutral/back) | 14 | 5 | 24 | 42 | 105 | 15 | **+12** | −12 | 25 | Spec §4.4 values; links Heavy at close range; cancels into the ultimate |
| Rift Break | toward + Special | 22 | 4 | 26 | 51 | 90 | 10 | KD | −15 | 0 | Travels 0.7 m (frames 4–18): one step in. D-127: was 1.4 m (frames 4–22), covered by a hop; knockdown. D-122: slower so the axe kick reads (was 16/4/22, −11) |
| Origin Surge | Ultimate at full meter | 20 | — | 10 | 30 | — | — | — | — | 100 | No hitbox; then 5 s Surge |
| Origin Break | Ultimate during Surge | 7 | 4 | 45 | 55 | 320 | 40 | KD | −28 | ≥ 30, spends all | Ends Surge; 60-tick hitstop (camera cinematic, skippable) |

- **Origin meter** 0–100: attacker gains per move (L 6/3, H 12/6, K 9/5,
  Rift 10/5 on hit/block); defender gains 20 % of damage taken, 3 per
  block. No gains during Surge. Never purchasable. Carries over between
  rounds of a match; resets each match. Training refills it.
- **Origin Surge (Kairo):** 300 ticks; meter drains to 0; damage ×1.15;
  specials cost no meter; ultimate available.
- **Knockdown:** 45 ticks down + 20 getting up, no hurtbox; ends the combo.
- **Routes:** spec §4.5 starter route **L, L, K, Origin Palm = 4 hits**
  (test enforced). Heavy follow-up after Palm only at close range. In Surge,
  Palm → Origin Break.
- **Infinite-combo guarantee (M6):** 3,120 runs — every 1–4 command route
  from {L, K, H, Special, toward+Special}, mid-screen/corner, full meter and
  free-special Surge — longest combo ≤ 5 hits, defender always recovers.

## Projectiles and parries (D-066)

- A projectile move (`projectile_speed > 0`) has no hitbox on the fighter.
  On its first active frame (`startup_frames`) a projectile appears at
  `hitbox_center` with `hitbox_size` and flies at `projectile_speed` m/s for
  at most `projectile_range` m (or to the arena wall). Total move length is
  still startup + active - 1 + recovery (Pulse Shot: 16 + 1 - 1 + 10 = 26).
- It resolves with the move's own damage, stun, pushback and hitstop:
  blocked by either guard, absorbed by armour, never caught by a counter
  stance or parry, passes through fighters without a hurtbox. One per
  fighter on screen. Two opposing projectiles cancel each other.
- A parry is a counter stance with no follow-up: the attacker is frozen for
  `counter_stun_frames` and the parrying fighter is neutral on the next
  tick after hitstop. Vexa's per-move table is in
  `docs/FIGHTER_COMBAT_DESIGN.md`.
