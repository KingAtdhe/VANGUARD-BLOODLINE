# Fighter Combat Design (summary)

Status: **five of six fighters built (Kairo, Drakon, Seraphina, Nox, Vexa — D-062
to D-066), awaiting the owner's test on a phone. Ryuen still uses the shared
set (KI-049).**

The full design (stance, footwork, attack tables with frame data, specials,
combos, defence, ultimate and animation personality per fighter) lives in the
owner's design doc: https://claude.ai/artifact/5EP9jJnUyoSHZCGf7G1yr1
This file is the in-repo summary; update both when the design changes.

## Roles

| Fighter | Style | Role | Range | Speed | Health |
| --- | --- | --- | --- | --- | --- |
| Kairo | Pressure boxing with street brawling | All-rounder, rushdown | Close to mid | Fast | Medium |
| Drakon | Heavy boxing and wrestling | Grappler, armoured bruiser | Close | Slow | Highest |
| Seraphina | Taekwondo and karate kicking | Long-range kicker | Long | Fast | Low |
| Nox | Ninjutsu and Silat, low and deceptive | Mix-up assassin | Close, in and out | Fastest | Lowest |
| Vexa | Muay Thai with a cybernetic arm | Zoner with close-range knees | Long and clinch | Medium | Medium |
| Ryuen | Tai Chi, Wing Chun and Aikido | Counter-fighter | Close | Slow feet, fast hands | Medium |

## Move sets (names only; frame data in the design doc)

| Fighter | Normals | Specials | Ultimate |
| --- | --- | --- | --- |
| Kairo | Jab, Cross, Body Hook, Low Kick | Origin Palm, Rift Break, Slip Counter | Origin Break |
| Drakon | Hammer Fist, Haymaker, Shoulder Check, Stomp | Forge Charge, Anvil Slam, Quake Stomp | Molten Colossus |
| Seraphina | Knife-hand, Side Kick, Roundhouse, Low Sweep | Crescent Arc, Halo Step, Seraph Dive | Radiant Ascension |
| Nox | Fang Jab, Rising Backfist, Scythe Sweep, Drop Heel | Shade Step, Feint Fang, Throat Pierce | Eclipse |
| Vexa | Piston Jab, Teep, Cut Kick, Slashing Elbow | Pulse Shot, Overclock Knee, Arc Guard | System Overdrive |
| Ryuen | Palm Heel, Chain Punch, Shin Stamp, Sinking Elbow | Returning Wave, Mountain Push, Flowing Step | Thousand Rivers |

## New mechanics the designs need

Each is new combat code plus tests, built before the moves that use it.
Balance values go in `data/`, never in controller code.

| Mechanic | Used by |
| --- | --- |
| Per-fighter move sets and frame data | All six |
| Low attacks and a low block | Nox, Seraphina, Vexa, Drakon, Kairo, Ryuen |
| Overhead attacks | Nox |
| Throws (unblockable grabs) | Drakon, Ryuen |
| Counter and parry | Ryuen, Vexa, Kairo |
| Armour (absorb one hit while attacking) | Drakon |
| Projectile | Vexa |
| Evasive dash with invulnerability, side switch | Nox, Seraphina, Ryuen |
| Launch and air hits (juggle) | Seraphina |

## Build order (proposed)

1. Keep the source rigs' finger bones in the game skeleton so fists close. **Done (D-060).**
2. Per-fighter move data, low attacks and low block. **Engine done (D-061): low block, hit levels, direction + button inputs. Move data per fighter follows with each fighter's set.**
3. Kairo's full set; owner tests on device before the rest follow. **Built (D-062), awaiting owner test.**
4. One fighter at a time with the mechanic it needs: Drakon (throws, armour — **built, D-063**),
   Seraphina (evade, launch — **built, D-064**), Nox (side switch, overhead — **built, D-065**), Vexa (projectile,
   parry — **built, D-066**), Ryuen (counters).
5. A test build after every fighter.

## Vexa as built (D-066)

| Move | Input | Frames | Notes |
| --- | --- | --- | --- |
| Piston Jab | L | 6 / 3 / 11 | Reach 1.15 m, the longest light. Cancels into itself, Teep, Slashing Elbow. Keyed. |
| Teep | H | 11 / 4 / 18 | 1.2 m pushback. Cancels into specials. Captured front kick, mirrored to the lead leg. |
| Cut Kick | K | 10 / 4 / 17 | LOW. Cancels into Slashing Elbow. Captured roundhouse reshaped into a low kick. |
| Slashing Elbow | down + H | 8 / 3 / 15 | Steps in 0.45 m, 80 damage, cancels into Overclock Knee. Keyed. |
| Pulse Shot | SP | fires on 16, 26 total | Projectile, 10 m/s, 7 m range, one on screen, 45 damage, no meter. Keyed. |
| Overclock Knee | toward + SP | 13 / 5 / 24 | Travels 1.7 m, knocks down, -16 on block, 25 meter. Keyed. |
| Arc Guard | away + SP | parry 3-11 of 30 | Parries one HIGH or MID hit, attacker frozen 26 frames, Vexa free at once. Lows, throws and projectiles beat it. Keyed. |
| System Overdrive | ULT in Surge | 9 / 4 / 46 | Short range, 300 damage, one hit. Keyed. |

Combos checked by tests: Jab, Teep, Pulse Shot (3 hits, ends far apart);
Cut Kick, Elbow, Knee (3 hits, needs 25 meter); Arc Guard parry, Elbow, Knee.
Missing against the design: counter-hit stagger on the Cut Kick, the
head-pull of the knee, separate hits and a beam in the ultimate, shield and
beam effects.

## Animation sources and limits

- Motion capture (CMU database, see `docs/LICENSES.md`) where a clip exists:
  boxing, guards, front kicks, karate strikes, falls, get-ups.
- Hand-keyed from captured poses where none exists: elbows, knees, sweeps,
  chain punches, cyber-arm moves, and all two-body throws (lowest expected
  quality).
- No cloth, hair or hood bones: those parts stay rigid.
- Every animation is checked in front, side and three-quarter renders, plus
  stretched-edge and floor-contact measurements. On-device look and
  performance can only be verified by the owner.
