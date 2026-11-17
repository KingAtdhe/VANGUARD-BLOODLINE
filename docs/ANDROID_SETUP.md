# Android setup and export

Status: preset committed, **no APK has been built yet**.

## One-time setup (on your machine)

1. Godot **4.7.2-stable** editor.
2. Export templates **4.7.2-stable**: *Editor → Manage Export Templates →
   Download and Install* (must match the editor version exactly).
3. Android SDK — easiest via Android Studio (*SDK Manager*): Platform-Tools,
   Build-Tools, one current SDK platform. Follow the JDK/SDK versions listed in
   the Godot 4.7 docs page *"Exporting for Android"*.
4. JDK 17 (OpenJDK).
5. *Editor → Editor Settings → Export → Android*: set **Android SDK Path** and
   **Java SDK Path**.
6. Debug keystore: Godot generates/uses one automatically if left empty in
   Editor Settings. Release keystore: create it yourself, keep it **outside**
   the repo, and enter its path/password in the export dialog. Godot stores
   these in `.godot/export_credentials.cfg` (git-ignored).

## Debug build on a device

1. Enable *Developer options → USB debugging* on the phone, connect via USB.
2. In Godot: *Project → Export → Android → Export Project* (debug) to
   `build/android/`, or use the one-click deploy (Android icon top-right).
3. Check: launches in landscape, rotating 180° flips correctly, never goes
   portrait, text is inside the safe area (notch/cutout), Quit works.

## Preset summary (`export_presets.cfg`)

- Package: `com.vanguardbloodline.prototype` (provisional — see D-008)
- Architectures: arm64-v8a
- Immersive (fullscreen) mode on
- Excludes `tests/`, `tools/`, `docs/`, `build/` from the PCK
- Signing fields empty — never commit keystores or passwords
