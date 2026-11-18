class_name CombatConstants
extends RefCounted
## Global combat simulation constants. All frame data is expressed in these
## ticks, never in render frames (spec §4.3, §9.4).

## Combat simulation rate in ticks per second.
const TICK_RATE: int = 60
## Seconds per combat tick (~16.67 ms).
const TICK_DELTA: float = 1.0 / TICK_RATE
## Maximum ticks simulated in one render frame. Prevents the "spiral of death"
## after a long stall (e.g. app resume); any extra elapsed time is dropped.
const MAX_CATCH_UP_TICKS: int = 5

## Player slots.
const P1: int = 0
const P2: int = 1
