# VANGUARD: BLOODLINE

## Complete Claude-Ready GitHub Production Package

**Document version:** 1.0\
**Project status:** Production specification / implementation blueprint\
**Target:** Android first, iOS planned\
**Orientation:** Landscape\
**Genre:** 3D one-on-one fighting game (2.5D combat)\
**Business model:** Free-to-play, fair monetization\
**Art direction:** Stylized realism\
**Combat direction:** Cinematic, responsive, skill-based\
**Engine:** Godot 4.x stable release, exact patch pinned at project
creation\
**3D pipeline:** Blender\
**Programming:** GDScript\
**Source control:** Git + GitHub\
**Explicit exclusion:** Unity is not used.

------------------------------------------------------------------------

# 0. Executive production brief

VANGUARD: BLOODLINE is an original mobile fighting game built around
readable, skill-based one-on-one combat presented with
stylized-realistic 3D characters and cinematic impact.

The camera presents a side-on fighting view. Fighters are fully 3D, but
the initial combat rules constrain them to a single horizontal fighting
plane. The game is designed for landscape touchscreens and Android-first
development.

The first production objective is not a large content release. It is a
polished, repeatable combat prototype that proves: 1. Touch input feels
immediate and reliable. 2. Two fighters can move, attack, defend, take
damage and complete a match. 3. Hit detection and attack timing are
deterministic and testable. 4. A basic opponent can fight without
cheating or reading future player input. 5. The project runs reliably on
real Android hardware.

The first public launch target is six playable fighters,
story/arcade/training content, and a small set of polished arenas.
Online PvP is explicitly deferred until after the offline game has been
validated.

## Non-negotiable product principles

-   Combat quality takes priority over roster size and cinematic
    spectacle.
-   No paid stat advantages, paid damage boosts, or paid competitive
    advantages.
-   The same core fighter must behave consistently at different graphics
    settings.
-   Cinematic camera effects must never hide important combat
    information or take control away during ordinary attacks.
-   All production assets must be original or properly licensed.
-   All gameplay systems must be modular, documented and testable.
-   Claude must preserve working project structure and inspect existing
    code before changing it.
-   Never use Unity, Unity packages, Unity project files or
    Unity-specific instructions.

## Scope boundaries

### Version 0.1 --- first playable prototype

-   One temporary playable fighter (Kairo).
-   One temporary AI opponent.
-   One greybox arena.
-   Landscape Android build.
-   Movement, facing, jump/crouch if included in the control design,
    light/heavy/kick attacks, block, hit reactions, health, round timer
    and match result.
-   Basic combo support and simple training/debug controls.
-   No account system, purchases, ads, online multiplayer or finished
    story.

### Launch target --- Version 1.0

-   Six playable fighters.
-   Three polished arenas, with a fourth optional story/boss arena if
    production capacity allows.
-   Story campaign, arcade mode, training mode and survival mode.
-   Character select, progression, cosmetics, save system and accessible
    settings.
-   Android release first.
-   iOS adaptation after Android performance and production pipeline are
    stable.

### Post-launch

-   Additional fighters and arenas.
-   Story chapters and cosmetic seasons.
-   Online PvP only after a separate networking design, security review
    and latency test programme.

------------------------------------------------------------------------

# 1. Game identity and creative direction

## 1.1 High concept

In 2096, humanity discovers an ancient energy source beneath the Earth's
crust known as **The Origin**. Exposure awakens extraordinary abilities
in some people, but prolonged contact changes their bodies and minds.

A secret organization, **The Ascendants**, stages an international
fighting tournament. The public believes the winner will become guardian
of The Origin. The tournament is actually a ritual intended to awaken an
intelligence buried beneath the planet.

The protagonist, Kairo, enters the tournament to discover what happened
to his missing brother and why his family is connected to The Origin.

## 1.2 Tone

-   Dramatic, mysterious and action-focused.
-   Stylized realism, not photorealism.
-   Strong silhouettes, readable materials and expressive faces.
-   Futuristic and ancient visual motifs can coexist, but each design
    must have a clear visual logic.
-   Combat can be intense and cinematic without relying on graphic gore.

## 1.3 Brand and IP safeguards

VANGUARD: BLOODLINE is a working title only. Before public commercial
use: - Search relevant game, software and entertainment trademarks in
target markets. - Check Google Play and Apple App Store name
availability. - Check domain and social handle availability. - Obtain
legal review for the final title and logo. - Do not use Mortal Kombat,
Street Fighter, or other existing franchises' names, characters,
costumes, moves, logos, music, UI, story elements or distinctive visual
designs in shipped assets. - Genre inspiration is acceptable; copying
protected expression is not.

------------------------------------------------------------------------

# 2. Product specification

## 2.1 Platform and display

-   First platform: Android.
-   Later platform: iOS.
-   Orientation: landscape only.
-   Initial design reference: 2400 × 1080 logical composition,
    responsive to aspect ratios.
-   UI must adapt to safe areas, cutouts, navigation bars and varying
    aspect ratios.
-   Avoid placing primary touch controls near system gesture edges.
-   Provide left-handed and right-handed control layouts.
-   Support UI scaling and button repositioning.

## 2.2 Camera and combat plane

Use a 2.5D fighting model: - Characters and arenas are 3D. - Main
movement is along the arena's horizontal X axis. - The camera is placed
on the arena's side and frames both fighters. - Fighters automatically
face their opponent. - Z-depth movement is disabled for the initial
prototype. Decorative arena depth is visual only. - Jumping and
crouching are optional vertical movement states; implement only after
grounded movement and attacks work. - Camera tracks the midpoint between
fighters with smoothing and bounded zoom. - Camera must not rotate
freely during normal combat. - Cinematic camera overrides are reserved
for selected special/ultimate moments and must return cleanly to
gameplay.

## 2.3 Match rules

Initial prototype defaults (tune during playtesting): -
One-versus-one. - Best of three rounds. - Round duration: 90 seconds. -
Health per fighter: 1,000 internal points. - Round ends when health
reaches zero or timer expires. - Timer expiry: fighter with more
remaining health wins; equal health triggers a draw or a configured
overtime rule. - Match ends when a fighter wins two rounds. - Training
mode can disable timer, damage or reset positions. - Pause is available
in offline modes. - Match result must be unambiguous and accessible.

These are starting values, not immutable balance promises.

## 2.4 Initial control layout

Landscape touchscreen: - Left virtual stick or directional pad: move
forward/backward; optional down/up for crouch/jump. - Light attack. -
Heavy attack. - Kick. - Block. - Special. - Ultimate (only when meter
threshold is reached).

Controls: - Buttons must have generous touch targets. - Buttons must
respond to touch-down, not only touch release, where appropriate. -
Support simultaneous movement and attack inputs. - Add input buffering
for attacks during recovery and transitions. - Avoid accidental
multi-touch cancellation. - Offer configurable button positions, size
and opacity. - Include a basic tutorial overlay. - All controls must
also be testable with keyboard/gamepad in editor builds.

### Suggested mobile layout

-   Left 28--35% of the screen: directional control.
-   Right 55--65%: action cluster.
-   Upper corners: health bars, timer and round indicators.
-   Special/ultimate indicators near the action cluster but not
    overlapping core buttons.
-   Keep the central combat area visually clear.

The final layout must be tested on several physical screen sizes.

------------------------------------------------------------------------

# 3. Launch roster

The launch target is six playable fighters. The initial production order
is Kairo, Drakon, Seraphina, Nox, Vexa and Ryuen. Morva and The
Sovereign remain planned story characters or future playable additions
unless scope and quality allow them to be added later.

Every playable fighter must have: - Distinct silhouette and
proportions. - Clear personality and visual theme. - A different combat
archetype. - A defined strengths/weaknesses profile. - A consistent base
animation set. - At least two special moves. - One Origin Surge state. -
One ultimate move. - Victory, defeat, hit, knockdown and recovery
reactions. - A readable colour/material identity.

## 3.1 Kairo --- The Exiled

Role: Balanced all-rounder; protagonist; recommended first playable
character.

-   Fighting style: hybrid martial arts.
-   Theme: red Origin energy.
-   Strengths: flexible range, approachable combos, reliable tools.
-   Weaknesses: no extreme specialization.
-   Signature moves: Origin Palm, Rift Break.
-   Ultimate: Origin Break --- a short, dramatic energy-powered
    sequence.
-   Design: athletic male fighter, dark combat clothing, restrained red
    energy accents. Avoid copying recognisable designs from existing
    fighting-game protagonists.

## 3.2 Drakon --- The Destroyer

Role: Heavy powerhouse.

-   Fighting style: heavy strikes, pressure and armour-breaking attacks.
-   Theme: heat and explosive force.
-   Strengths: high damage and strong punish opportunities.
-   Weaknesses: slower startup and recovery.
-   Signature moves: Furnace Fist, Ground Rupture.
-   Ultimate: Cataclysm Driver.
-   Design: large, powerful silhouette, industrial protective elements
    and orange energy details.

## 3.3 Seraphina --- The Ghost

Role: Fast precision fighter.

-   Fighting style: evasive movement, feints and rapid strings.
-   Theme: blue-white illusion energy.
-   Strengths: mobility and quick openings.
-   Weaknesses: lower individual hit damage and fragile defense.
-   Signature moves: Phantom Step, Mirror Strike.
-   Ultimate: Phantom Collapse.
-   Design: agile silhouette, light armour, layered fabric and
    restrained blue-white effects.

## 3.4 Nox --- The Shadow

Role: Counter and deception specialist.

-   Fighting style: baiting, counters and mix-ups.
-   Theme: violet shadow energy.
-   Strengths: punishes predictable attacks.
-   Weaknesses: requires timing and matchup knowledge.
-   Signature moves: Veil Counter, Night Snare.
-   Ultimate: Eclipse Sentence.
-   Design: masked, compact silhouette with violet energy accents. Do
    not use generic copyrighted ninja iconography or recognisable
    franchise costume patterns.

## 3.5 Vexa --- The Machine

Role: Technical space-control fighter.

-   Fighting style: mechanical tools, controlled ranged pressure and
    traps.
-   Theme: electric red/white energy.
-   Strengths: controls distance and creates setup opportunities.
-   Weaknesses: vulnerable when opponents get close.
-   Signature moves: Arc Pulse, Magnetic Lock.
-   Ultimate: System Overload.
-   Design: cybernetic fighter with a clear human silhouette, readable
    mechanical details and controlled electrical effects.

## 3.6 Ryuen --- The Ancient

Role: Defensive specialist.

-   Fighting style: traditional martial arts, parries and measured
    counterattacks.
-   Theme: gold energy.
-   Strengths: defensive reads and punish windows.
-   Weaknesses: limited mobility and requires patience.
-   Signature moves: Stillwater Guard, Meridian Strike.
-   Ultimate: Thousandfold Return.
-   Design: experienced martial artist with layered garments and
    restrained gold accents. Avoid direct imitation of known
    martial-arts characters.

## 3.7 Boss/story characters

-   Morva --- grappling and poison/biological transformation theme.
-   The Sovereign --- final antagonist with a multi-style moveset.
-   Boss versions must be balanced for offline story encounters and
    should not be used as competitive fighters until properly tuned.

------------------------------------------------------------------------

# 4. Combat design

## 4.1 Core combat loop

1.  Read opponent distance and state.
2.  Approach, retreat or hold position.
3.  Create an opening through movement, pressure or a defensive read.
4.  Start an attack.
5.  Confirm whether the attack hits, is blocked or misses.
6.  Continue a valid combo, stop safely or recover.
7.  Defend against the opponent's response.
8.  Build Origin energy through combat.
9.  Use a special or earned ultimate at the correct moment.
10. Win the round through better decisions and execution.

## 4.2 Combat pillars

**Responsiveness:** Input must feel immediate. Input buffering and
animation cancel rules must be deliberate.

**Readability:** Attack startup, range, hit effect and recovery should
be visually understandable.

**Skill:** Timing, spacing, defense, matchup knowledge and combo
execution must matter.

**Fairness:** No paid gameplay power. AI opponents must obey the same
movement, hitbox, recovery and resource rules as players.

**Cinematic impact:** Strong attacks use controlled hit-stop, camera
shake, sound, particles and selected slow-motion moments without
disrupting ordinary control.

## 4.3 Move data model

Do not hardcode individual attacks inside fighter controllers. Store
attack definitions in JSON or Godot Resources. Use a consistent schema.

Each attack should define: - `id` - `display_name` - `input_pattern` -
`animation` - `startup_frames` - `active_frames` - `recovery_frames` -
`damage` - `chip_damage` - `hitstun_frames` - `blockstun_frames` -
`pushback` - `hit_level` (high, mid, low, throw, projectile) -
`hitbox_profile` - `cancel_tags` - `meter_gain_on_hit` -
`meter_gain_on_block` - `meter_cost` - `knockdown` - `launch` -
`airborne_allowed` - `cooldown` only if the move design genuinely needs
one.

Frame counts must use the combat simulation rate, not render FPS. For a
60 Hz combat simulation, one frame is approximately 16.67 ms.

## 4.4 Initial combat frame-data examples

These are prototype starting values for testing, not final competitive
balance:

  -----------------------------------------------------------------------------
  Move             Startup       Active     Recovery       Damage Notes
  ----------- ------------ ------------ ------------ ------------ -------------
  Kairo light           5f           3f          10f           35 Fast
  punch                                                           close-range
                                                                  check

  Kairo heavy          12f           3f          19f           85 Higher
  punch                                                           commitment

  Kairo kick            9f           4f          15f           60 Mid-range
                                                                  attack

  Kairo                14f           5f          24f          105 Special;
  Origin Palm                                                     meter cost

  Drakon               16f           4f          25f          120 Slow,
  heavy                                                           powerful
  strike                                                          

  Seraphina             4f           2f           9f           25 Very fast,
  quick                                                           low damage
  strike                                                          

  Ryuen                 3f      defined          18f           90 Requires
  counter       activation       window                           correct
  stance                                                          timing
  -----------------------------------------------------------------------------

Implementation notes: - The move's active hitbox exists only during
active frames. - Startup and recovery must be visible in animation. - A
move cannot hit more than once per target unless explicitly
configured. - Hitstop should pause combat actors according to a central
hitstop system, not by independently changing timers in multiple
scripts. - Use a fixed combat tick and deterministic update ordering. -
Define whether hitboxes are sampled once per tick or swept between
positions to prevent tunnelling. - Block direction and high/low rules
must be documented and tested. - Throws need a clear startup and
escape/counter rule.

## 4.5 Combo system

-   Combos are authored as valid cancel routes.
-   Each attack can specify permitted cancel tags.
-   Input buffer stores recent inputs for a short configurable window.
-   Combo counter increments only when a new hit is confirmed.
-   Combo scaling reduces damage on longer combos.
-   Air launch and juggle rules must be bounded to prevent infinite
    combos.
-   Reset combo state on neutral recovery, knockdown or configured
    escape.
-   Training mode displays damage, combo count, frame data and input
    history.

Example Kairo starter route: 1. Light punch. 2. Light punch. 3. Forward
kick. 4. Origin Palm. 5. Follow-up heavy strike if the hit state allows
it.

The actual route must be tested for hitstun, distance and cancel
validity.

## 4.6 Origin Surge

-   Meter range: 0--100.
-   Meter gain from confirmed hits, successful defense and taking
    damage, with carefully tuned weights.
-   Meter cannot be purchased.
-   Enhanced state requires a full meter.
-   Activation has a readable startup and a clear visual/audio cue.
-   Duration and enhanced properties are defined per fighter.
-   Ultimate consumes the configured meter amount.
-   Meter rules must be consistent across all modes.

## 4.7 Cinematic rules

-   Standard hits: short hit-stop, subtle shake, small impact effect.
-   Heavy hits: stronger hit-stop and controlled camera response.
-   Specials: character-specific effects and sound.
-   Ultimate: short cinematic sequence with optional skip.
-   No camera effect may hide health, timer or fighter positions.
-   Provide reduced camera shake and reduced flashes settings.
-   Avoid rapid flashing effects and provide accessibility options.
-   Do not slow down online simulation if PvP is added later; online
    cinematics must be presentation-only or synchronised by a carefully
    designed protocol.

------------------------------------------------------------------------

# 5. Opponent AI

The first AI should use a finite-state machine, not a machine-learning
model.

Suggested states: - `NEUTRAL` - `APPROACH` - `RETREAT` - `ATTACK` -
`BLOCK` - `PUNISH` - `RECOVER` - `STUNNED` - `KNOCKDOWN` - `WAKEUP`

AI requirements: - React only to information available to a human
player. - Do not read future player input. - Do not bypass
startup/recovery or hit detection. - Use configurable reaction delay. -
Use distance bands and move-selection weights. - Respect meter and
cooldown rules. - Provide difficulty through reaction time, decision
quality and move selection---not hidden damage multipliers. - Add
predictable patterns at low difficulty and more adaptive decision-making
at higher difficulty. - Record AI decisions in debug builds for tuning.

Difficulty presets: - Beginner: slower reactions, fewer defensive
responses, simple attack patterns. - Standard: balanced offense and
defense. - Expert: better spacing, punish recognition and combo
selection, still subject to normal rules.

------------------------------------------------------------------------

# 6. Game modes and progression

## 6.1 Launch modes

**Story** - Kairo-focused campaign. - Short scenes between fights. - Six
chapters planned. - Unique boss encounter. - Story rewards include
cosmetics, profile items and character unlock progress.

**Arcade** - Select a fighter. - Fight a sequence of opponents. - Finish
with a boss or rival encounter. - Award score, currency and mastery XP.

**Training** - Dummy behavior settings. - Reset positions and health. -
Infinite time option. - Damage and combo display. - Input history. -
Frame-data inspection in advanced mode.

**Survival** - Increasingly difficult sequence of opponents. - Limited
recovery between matches. - Reward based on progress and performance.

## 6.2 Progression

-   Account level.
-   Character mastery level.
-   Earnable soft currency.
-   Daily/weekly challenges only if a reliable live-operations plan
    exists.
-   Cosmetic unlocks.
-   Fighter unlocks through play.
-   Story and arcade completion rewards.

Avoid manipulative energy systems that prevent players from playing the
core fighting game.

## 6.3 Save data

Store: - Settings. - Story progress. - Unlocked fighters. - Earned
cosmetics. - Character mastery. - Soft-currency balance. - Tutorial
completion. - Match statistics.

For offline prototype, local save data is acceptable. For launch
purchases and premium currency, server-side entitlement and transaction
validation are required. Do not trust a client-only balance for paid
currency.

------------------------------------------------------------------------

# 7. Monetization design

## 7.1 Principles

-   Free download.
-   Core fighting is free.
-   No paid damage, health, speed, combo or meter advantage.
-   No paid-only fighter advantage in competitive modes.
-   No forced advertisements during a match.
-   No paid random loot boxes in the initial business model.
-   Clearly disclose prices and purchase terms.

## 7.2 Proposed monetization

-   Optional character costumes.
-   Cosmetic skin bundles.
-   Visual entrance/victory effects.
-   Profile frames, titles and banners.
-   Arena appearance packs.
-   Optional season pass with cosmetic rewards.
-   Optional rewarded ad for a small, capped bonus in suitable menus.

Fighters should be earnable through play. Paid instant unlocks can be
considered only if the same fighter is also reasonably earnable without
payment and all competitive players have equivalent access.

## 7.3 Monetization implementation sequence

Do not build payment integration during the first prototype. 1. Build
progression and unlock interfaces with test data. 2. Add a currency
ledger and transaction history model. 3. Select platform-compliant
billing SDK/provider after platform and region review. 4. Validate
receipts/transactions server-side. 5. Add restore-purchases flow. 6.
Test refunds, interrupted purchases and duplicate callbacks. 7. Add
optional advertising only after privacy and consent review. 8. Review
local laws, age ratings, consumer law and store policies before release.

------------------------------------------------------------------------

# 8. Art direction and Blender pipeline

## 8.1 Style target

Stylized realism: - Human proportions with slightly exaggerated
silhouettes. - Detailed but clean facial features. - Physically based
materials with controlled roughness. - Strong colour separation. -
Readable costumes at mobile resolution. - Distinctive silhouettes. -
Moderate detail density; avoid tiny surface noise. - Effects that
support readability rather than obscure attacks.

## 8.2 Character asset specification

Each final fighter should include: - One game-ready body mesh. -
Separate head/face mesh where appropriate. - Modular costume parts where
practical. - Hair/cloth meshes with performance-conscious geometry. -
Standard humanoid skeleton. - Consistent bone naming. - Skin weights
tested at extreme combat poses. - Material slots kept manageable. - LODs
or reduced mesh variants where needed. - Collision/ground reference
markers if required. - Animation library. - Thumbnail/portrait render. -
In-game preview pose.

Do not create separate skeleton conventions for every fighter unless a
design genuinely requires it.

## 8.3 Blender export conventions

Recommended: - Work in metric units. - Establish a shared character
scale and ground plane. - Apply transforms before export. - Set
consistent forward/up axes and validate orientation in Godot. - Use glTF
2.0 (`.glb`) for character, animation and environment interchange. -
Keep source `.blend` files in the art source archive or repository using
Git LFS if they become large. - Export final game-ready `.glb` files to
the Godot project. - Test skeletal animation, material import and root
motion behavior in-engine. - Do not assume Blender and Godot use
identical axis conventions; validate with a test asset first.

## 8.4 Character animation list

Base set for every playable fighter: - Idle loop. - Idle variation. -
Walk forward. - Walk backward. - Dash forward. - Dash backward. - Crouch
idle. - Crouch transition. - Jump start, airborne and landing if jumping
is supported. - Light attack. - Heavy attack. - Kick. - Block high. -
Block low if low attacks are included. - Hit reaction light. - Hit
reaction heavy. - Knockdown. - Get-up. - Throw start/receive where
applicable. - Special move 1. - Special move 2. - Ultimate. - Victory. -
Defeat.

Animation naming: `FIGHTER_ACTION_VARIANT` Examples: - `KAIRO_IDLE_A` -
`KAIRO_ATTACK_LIGHT_01` - `KAIRO_HIT_HEAVY` -
`KAIRO_SPECIAL_ORIGIN_PALM` - `KAIRO_ULTIMATE_ORIGIN_BREAK`

Animations must have clear start/end states and must be tested for foot
sliding, root motion, weapon/prop clipping and hitbox alignment.

## 8.5 Initial arena asset list

Arena 01 --- Ascendant Arena: - Main floor and boundaries. - Background
architecture. - Tournament signage with original fictional branding. -
Lighting fixtures. - Ambient particles. - Background animation. -
Collision boundary markers.

Arena 02 --- Forgotten Temple: - Floor, pillars and stairs. - Ancient
energy structures. - Background ruins. - Controlled fog/particles. -
Baked lighting.

Arena 03 --- Neon District: - Rooftop floor. - Distant city skyline. -
Neon signs with original fictional text. - Atmospheric lighting. -
Limited animated background props.

Arena 04 --- Origin Chamber (optional launch/story boss arena): -
Central energy structure. - Ancient architecture. - Controlled animated
energy effects. - Strong final-boss composition.

## 8.6 Art performance budgets

These are initial budgets to validate with real builds, not rigid engine
limits: - Character mesh target: approximately 25k--45k triangles for a
main fighter, with LODs. - Avoid excessive material slots; target 3--6
character materials where practical. - Use texture atlases where
suitable. - Use compressed textures and mipmaps. - Limit transparent
overdraw and full-screen effects. - Keep particle counts bounded. - Use
baked/static lighting where practical. - Profile GPU and CPU
separately. - Provide low/medium/high graphics settings.

Never sacrifice animation readability to meet a polygon target; profile
first and optimize the actual bottleneck.

------------------------------------------------------------------------

# 9. Godot technical architecture

## 9.1 Engine version and renderer

-   Use a current stable Godot 4.x release.
-   Pin the exact Godot patch version in `README.md` and build
    documentation.
-   Do not update engine versions mid-milestone without a tested
    migration.
-   Start with the Mobile renderer for Android testing.
-   Keep a compatibility test scene for lower-end devices.
-   Use GDScript initially to reduce tooling and build complexity.
-   Use typed GDScript where practical.
-   Avoid adding third-party plugins until their maintenance, licensing
    and Android compatibility are reviewed.

## 9.2 Scene structure

Suggested scene tree:

``` text
Main
├── AppState
├── SceneRouter
├── AudioManager
├── SaveManager
├── UI
└── CurrentScreen
```

Combat scene:

``` text
CombatScene
├── ArenaRoot
│   ├── StageGeometry
│   ├── Background
│   ├── Lighting
│   └── ArenaBounds
├── CameraRig
├── FighterSpawner
├── Fighter1
├── Fighter2
├── CombatManager
├── HitboxManager
├── EffectsManager
├── AudioManager
├── MatchHUD
└── DebugOverlay
```

Fighter scene:

``` text
Fighter
├── CharacterBody3D
├── VisualRoot
│   ├── Skeleton3D
│   ├── MeshInstance3D
│   └── AnimationTree
├── HurtboxRoot
├── AttackOrigin
├── StateMachine
└── FighterAudio
```

The exact nodes may change during prototyping, but scene
responsibilities must remain clear.

## 9.3 Systems and responsibilities

**GameState / SceneRouter** - Main menu, fighter select, loading, combat
and results. - Prevent multiple combat scenes from being active. -
Handle scene transitions and pause state.

**InputRouter** - Read touch, keyboard and gamepad input. - Convert
input to logical actions. - Support remapping and left-handed layout. -
Avoid direct combat logic inside UI button scripts.

**FighterController** - Movement and facing. - Current state. - Input
buffer. - Requests actions from combat system. - No direct ownership of
match rules.

**CombatManager** - Match clock and rounds. - Damage application. -
Hit/block/throw resolution. - Combo state. - Meter and round
transitions.

**HitboxManager** - Activate attack regions during configured frames. -
Resolve hurtbox overlap. - Prevent duplicate hits. - Apply priority and
clash rules if supported. - Record hit events for debugging.

**AnimationController** - Play and transition animations. - Receive
combat state. - Send animation events only where necessary. - Do not use
animation playback position as the only authoritative combat timer.

**AIController** - Select actions based on observed state. - Apply
reaction delay. - Use same combat requests as player controller.

**CameraRig** - Track fighters. - Keep both visible. - Enforce camera
bounds. - Apply controlled cinematic overrides.

**ProgressionManager** - Award rewards. - Track unlocks and mastery. -
Separate earned and purchased currencies.

**SaveManager** - Versioned save schema. - Validation and recovery. - Do
not store payment authority solely in local files.

## 9.4 Fixed combat simulation

Fighting logic must not depend directly on variable render frame rate.

Recommended approach: - Run combat decisions on a fixed 60 Hz tick. -
Render independently. - Accumulate elapsed time and process fixed
ticks. - Cap catch-up ticks to avoid a spiral of death. - Use a central
ordering for movement, attack activation, collision, hit resolution and
state transitions. - Record combat events with tick numbers for
debugging.

If a fixed-tick architecture is too complex for the first greybox,
implement the simplest correct version and refactor before adding
complex combos. Do not mix arbitrary timers and animation callbacks
across many scripts.

## 9.5 Data-driven fighter and move resources

Suggested fighter definition: - Fighter ID. - Display name. - Portrait
path. - Scene path. - Base health. - Movement profile. - Combat
archetype. - Animation mapping. - Move list. - Origin Surge
configuration. - Audio configuration. - Cosmetic slots.

Suggested move definition: - Move ID. - Input pattern. - Animation ID. -
Frame data. - Damage and hitstun. - Blockstun and pushback. - Hit
level. - Hitbox profile. - Meter gain/cost. - Cancel tags. - Special
behavior flags.

Use typed custom Resources if they improve editor validation; JSON is
useful for simple externally editable balance tables. Pick one canonical
representation and document it. Do not maintain two conflicting sources
of truth.

## 9.6 Save-data versioning

Every save must include: - Schema version. - Timestamp. - Settings. -
Progress. - Unlocks. - Currency. - Character mastery.

On load: - Validate structure and value ranges. - Migrate older
schemas. - Recover from corrupt saves with a safe default. - Never
silently grant premium currency from client data. - Do not store secrets
or service credentials in the game client.

------------------------------------------------------------------------

# 10. Proposed repository structure

``` text
VANGUARD-BLOODLINE/
├── project.godot
├── README.md
├── LICENSES.md
├── CHANGELOG.md
├── .gitignore
├── .gitattributes
├── addons/
├── assets/
│   ├── characters/
│   │   ├── kairo/
│   │   ├── drakon/
│   │   ├── seraphina/
│   │   ├── nox/
│   │   ├── vexa/
│   │   └── ryuen/
│   ├── arenas/
│   ├── animations/
│   ├── audio/
│   ├── materials/
│   ├── effects/
│   └── ui/
├── data/
│   ├── fighters/
│   ├── moves/
│   ├── combos/
│   ├── ai/
│   └── progression/
├── scenes/
│   ├── app/
│   ├── menus/
│   ├── combat/
│   ├── fighters/
│   ├── arenas/
│   └── ui/
├── scripts/
│   ├── app/
│   ├── input/
│   ├── combat/
│   ├── fighters/
│   ├── ai/
│   ├── camera/
│   ├── progression/
│   ├── save/
│   └── ui/
├── audio/
├── localization/
├── tests/
│   ├── unit/
│   ├── integration/
│   └── device/
├── docs/
│   ├── GAME_DESIGN.md
│   ├── TECHNICAL_ARCHITECTURE.md
│   ├── COMBAT_FRAME_DATA.md
│   ├── BLENDER_PIPELINE.md
│   ├── ART_BIBLE.md
│   ├── MOBILE_PERFORMANCE.md
│   ├── MONETIZATION.md
│   ├── QA_PLAN.md
│   ├── RELEASE_CHECKLIST.md
│   └── DECISION_LOG.md
└── build/
    └── README.md
```

Use Git LFS for large `.blend`, source video, high-resolution textures
or other binary source assets if needed. Do not commit generated build
outputs, secrets, signing keys, keystores, API tokens or private
credentials.

------------------------------------------------------------------------

# 11. Claude implementation rules

These instructions should be included in the repository as `CLAUDE.md`.

## Claude's role

You are the lead Godot gameplay engineer and technical implementation
partner for VANGUARD: BLOODLINE.

Your job is to implement the approved specification in the existing
GitHub repository. You must not redesign the game, change the engine, or
introduce unrelated systems without approval.

## Mandatory rules

1.  Read `CLAUDE.md`, `README.md` and relevant documents before making
    changes.
2.  Inspect the existing project tree and current Git status before
    editing.
3.  Never use Unity or Unity-specific technology.
4.  Use Godot 4.x and GDScript unless a documented decision approves
    otherwise.
5.  Implement one milestone or clearly bounded task at a time.
6.  Do not replace a working system just because a different
    architecture is preferred.
7.  Do not delete or rename files without checking references and
    explaining the reason.
8.  Do not invent missing art assets. Use labelled placeholders until
    Blender assets exist.
9.  Keep gameplay balance data separate from controller code.
10. Use typed GDScript and clear naming.
11. Avoid giant monolithic scripts.
12. Add comments for non-obvious combat timing and state transitions.
13. Handle null references and scene lifecycle correctly.
14. Do not claim a build or test passed unless it was actually run.
15. When a tool or device is unavailable, clearly report what remains
    unverified.
16. Keep the README and decision log updated.
17. Never put secrets, signing credentials or private tokens in source
    control.
18. Preserve Android landscape orientation.
19. Do not add online multiplayer, ads or billing before their approved
    milestone.
20. Never make paid gameplay advantages.

## Required response after every implementation task

Claude must report: - Files created. - Files modified. - Systems
implemented. - Tests run and their actual results. - Build/export
status. - Known issues. - Exact next task. - Any manual Blender or
Android Studio action needed.

## Definition of done

A task is complete only when: - The feature exists in the project. - It
is connected to the actual game flow. - It has no known parse/runtime
errors in the tested environment. - Relevant tests pass. - It has been
manually verified where automation is insufficient. - Documentation is
updated. - No unrelated features were silently changed.

------------------------------------------------------------------------

# 12. Implementation backlog and acceptance criteria

## Milestone 0 --- repository and project setup

Tasks: - Create repository. - Add `CLAUDE.md`. - Add design and
technical documents. - Create Godot project. - Configure landscape
orientation. - Configure input actions. - Configure Mobile renderer. -
Add a boot scene. - Add placeholder assets. - Add a basic Android export
preset without committing secrets.

Acceptance: - Project opens in the pinned Godot version. - Main scene
launches. - Landscape orientation is correct on a test device. - No
missing resource errors. - Git repository is clean after the milestone
commit.

## Milestone 1 --- greybox arena and fighters

Tasks: - Create greybox stage. - Create two capsule/primitive
fighters. - Add camera rig. - Add fighter spawn points. - Add arena
boundaries. - Add movement and facing. - Add basic debug display.

Acceptance: - Both fighters remain within the arena. - They face each
other correctly. - Camera keeps both fighters visible. - Movement works
at different render frame rates.

## Milestone 2 --- attacks and hit detection

Tasks: - Create attack data model. - Create hurtbox and hitbox system. -
Add light, heavy and kick attacks. - Add block. - Add damage and hit
reaction. - Add hit-stop and basic effects. - Add combat log.

Acceptance: - Active hitboxes only exist during active frames. - One
attack cannot accidentally hit the same opponent repeatedly. - Blocking
and damage rules are consistent. - Hit detection is reproducible and
debuggable.

## Milestone 3 --- match loop

Tasks: - Add health bars. - Add timer. - Add round counter. - Add
best-of-three logic. - Add win/lose results. - Add rematch. - Add pause.

Acceptance: - Match always reaches a valid end state. - Timer and health
cannot become invalid. - Round transitions reset positions and state
correctly. - Rematch starts a clean match.

## Milestone 4 --- combo and input systems

Tasks: - Add touch controls. - Add keyboard/gamepad debug controls. -
Add input buffer. - Add cancel routes. - Add combo counter and
scaling. - Add training reset. - Add input history.

Acceptance: - Simultaneous movement and attack works. - Buffered inputs
execute only when legal. - Invalid cancel routes are rejected. - No
infinite combo is possible in the tested move set.

## Milestone 5 --- AI

Tasks: - Add AI state machine. - Add distance evaluation. - Add attack
selection. - Add block/punish behavior. - Add difficulty settings. - Add
decision logging.

Acceptance: - AI uses the same legal combat actions as the player. - AI
does not read future input. - Each difficulty is distinguishable. - AI
can be defeated and does not become idle permanently.

## Milestone 6 --- Kairo vertical slice

Tasks: - Create final Kairo model in Blender. - Rig and skin. - Export
to GLB. - Import into Godot. - Add animation state machine. - Add full
base animation set. - Add two special moves. - Add Origin Surge and
ultimate. - Add voice/sound placeholders then final audio.

Acceptance: - Kairo can complete a full match. - Animations transition
cleanly. - No severe mesh deformation. - Hitboxes align with attacks. -
Performance meets agreed device target.

## Milestone 7 --- UI, menus and modes

Tasks: - Main menu. - Fighter select. - Story mode flow. - Arcade
mode. - Training mode. - Survival mode. - Results screen. - Settings. -
Save/load.

Acceptance: - Every menu has working navigation. - No dead-end
screens. - Progress persists after app restart. - Settings persist. -
Training tools work.

## Milestone 8 --- remaining fighters and arenas

Tasks: - Produce Drakon and Seraphina. - Complete Nox, Vexa and Ryuen. -
Create remaining arenas. - Add fighter-specific audio and effects. - Add
balance tests.

Acceptance: - Six fighters can be selected and played. - Each has a
unique archetype and complete moveset. - No fighter has a pay-to-win
advantage. - Each arena meets mobile performance budget.

## Milestone 9 --- release preparation

Tasks: - Android profiling and optimization. - Device compatibility
testing. - Save migration tests. - Privacy and consent review. -
Monetization integration only after provider selection. - Store listing
and original promotional art. - Crash reporting and analytics with
privacy review. - Closed testing. - Release candidate.

Acceptance: - No critical crashes in test suite. - No known progression
blockers. - Purchases are validated correctly if enabled. - Privacy
policy and store declarations are complete. - Release build signed
through secure local/CI configuration.

------------------------------------------------------------------------

# 13. QA and device testing

Test on real devices as early as possible.

Test matrix: - Lower-end supported Android device. - Mid-range Android
device. - Higher-end Android device. - Different aspect ratios. -
Different refresh rates. - Touch input while multiple buttons are
held. - App pause/resume during a match. - Incoming phone call or system
interruption. - Low battery/performance mode. - Device thermal
throttling. - Save and restore. - Offline launch. - Audio
interruption. - Accessibility settings.

Combat QA: - Every attack at minimum, typical and maximum range. - Every
attack against block. - Hit during startup. - Hit during recovery. -
Simultaneous attack clashes. - Round ending during hit-stop. - Knockdown
and wake-up. - Combo scaling. - Meter gain/cost. - AI reaction delay. -
Camera bounds at extreme distances.

Performance: - Profile CPU, GPU, memory and frame-time. - Target 60 FPS
on the chosen supported devices. - If 60 FPS cannot be maintained,
define a consistent lower target rather than allowing unstable frame
pacing. - Never change gameplay timing based on graphics quality. - Test
prolonged play sessions for heat and throttling.

------------------------------------------------------------------------

# 14. Build and release workflow

## Android first

1.  Pin the Godot version.
2.  Install matching Android export templates.
3.  Configure Android SDK/JDK according to the pinned Godot
    documentation.
4.  Create a debug export.
5.  Install on a physical Android device.
6.  Test touch, orientation, audio, save and performance.
7.  Configure release signing securely.
8.  Build a release artifact.
9.  Test internal distribution before public release.

Never commit keystores, passwords, signing files or service credentials.

## iOS later

-   Requires access to macOS and Xcode for the official iOS
    export/signing workflow.
-   Validate plugin and SDK compatibility.
-   Re-test safe areas, touch controls, audio and performance.
-   Complete Apple review and privacy requirements.

## CI

Start with: - GitHub repository checks. - Static project validation
where practical. - GDScript linting or formatting if selected. -
Automated unit tests for combat data and match rules. - Export
validation when a suitable runner is configured.

Do not pretend that a CI build proves device performance. Physical
device testing remains required.

------------------------------------------------------------------------

# 15. First Claude task --- copy and send

Use this as the first instruction to Claude after creating the GitHub
repository and placing this production package in `docs/`.

------------------------------------------------------------------------

You are now the lead Godot 4.x developer for VANGUARD: BLOODLINE.

Read the complete production specification before writing code.

The game is a landscape, Android-first, stylized-realistic 3D one-on-one
fighting game. It uses Godot 4.x and GDScript. Blender is used for 3D
assets. The project is managed in GitHub. Unity must not be used.

Your first assignment is **Milestone 0 only**.

1.  Inspect the repository and its Git status.
2.  Read the complete game specification and create `CLAUDE.md` from its
    mandatory development rules.
3.  Create the Godot project structure.
4.  Create a minimal boot scene and main menu placeholder.
5.  Configure landscape orientation and the initial input map.
6.  Configure the Mobile renderer and Android export documentation.
7.  Add placeholder assets only; do not create the final characters or
    arenas yet.
8.  Add a README with the exact Godot version, setup instructions and
    current project status.
9.  Add a decision log and initial milestone checklist.
10. Validate that the project opens and the main scene runs if the
    required tools are available.

Do not implement combat, AI, progression, purchases, advertisements,
online multiplayer or final 3D assets in this task.

Do not invent test results. Report every file created or modified, all
tests actually run, anything not verified, and the exact next task.

Stop after Milestone 0. Wait for approval before starting Milestone 1.

------------------------------------------------------------------------

# 16. Project governance

Use these rules for the entire project:

-   One milestone at a time.
-   Review Git diff before accepting changes.
-   Keep a known-good build at each milestone.
-   Tag major milestones in Git.
-   Do not combine unrelated refactors with feature work.
-   Keep a `DECISION_LOG.md` for engine, architecture, balance and
    art-pipeline decisions.
-   Keep a `KNOWN_ISSUES.md` or issue tracker for bugs.
-   Never overwrite the only copy of source art.
-   Back up Blender source files.
-   Review all external assets and plugins for license compatibility.
-   Keep store, privacy and payment requirements separate from gameplay
    code.
-   Do not start online PvP just because the offline prototype works; it
    requires a dedicated technical milestone.

------------------------------------------------------------------------

# 17. Final production definition

VANGUARD: BLOODLINE is ready for its first public release only when:

-   Combat feels responsive and fair.
-   Six fighters are complete and sufficiently distinct.
-   Story, arcade, training and survival modes work.
-   The game is stable on the supported Android device range.
-   Controls are comfortable in landscape.
-   Progress and unlocks save correctly.
-   Monetization is optional and does not sell competitive power.
-   All assets have cleared licensing and ownership checks.
-   Store listing, privacy disclosures and age rating are complete.
-   A release candidate has passed internal testing.

**The first goal is not to build the biggest fighting game. It is to
build a fighting game whose combat is so satisfying that players want
another match.**
