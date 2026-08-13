# Game profiles

A `GameProfile` records every environmental assumption a recorded route depends
on: display, window, DPI, view, FOV, sensitivity, HUD language, key bindings,
HUD crop regions and the fitted coordinate / movement / mouse-turn calibrations.

A route stores the **fingerprint** of the profile it was recorded under. The
fingerprint hashes only the fields that would invalidate the route if they
changed (resolution, DPI, view, FOV, sensitivity, language, key bindings,
coordinate transform), so replaying a route against a changed profile is
refused rather than silently attempted.

Print a profile's fingerprint and readiness:

```powershell
python -c "from pubg_training_bot.config import load_game_profile; p=load_game_profile('dev-1080p-fpp'); print(p.fingerprint); print(p.missing_for_navigation())"
```

| File | State |
| --- | --- |
| `dev-1080p-fpp.yaml` | Uncalibrated Stage 0 placeholder. Not usable for navigation. |

Stage 2 produces the first profile with real crops and window geometry;
Stage 4 fills in the coordinate, movement and mouse-turn calibrations.
